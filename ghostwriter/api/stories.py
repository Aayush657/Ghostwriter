"""Story routes: upload a recording, list the archive, read, edit, re-read, listen again and delete one
story, play its audio, retry a failure, and the things Gemma writes about it."""

from __future__ import annotations

import threading
import uuid
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Form, HTTPException, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field, StringConstraints

from ghostwriter import audio, db, llm, pipeline, prompts, trash, tts
from ghostwriter.api.sse import sse, stream
from ghostwriter.audio import ALLOWED_EXTENSIONS, AudioError
from ghostwriter.config import settings
from ghostwriter.llm import LLMError
from ghostwriter.models import Mood, Title

router = APIRouter(prefix="/api/stories", tags=["stories"])

MAX_UPLOAD_BYTES = 200 * 1024 * 1024
CHUNK_BYTES = 1024 * 1024
Language = Literal["auto", "en", "hi", "hinglish"]


@router.post("", status_code=201)
async def upload_story(
    background: BackgroundTasks,
    file: UploadFile,
    answers_question_id: int | None = Form(None),
    language: Language = Form("auto"),
) -> dict:
    """Check the file really is audio, save it untouched, then transcribe and analyse it in the background.

    Nothing is saved for a file that isn't a usable recording: the page shows why, under the upload.
    """
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise HTTPException(415, f"The ghost can't read '{ext or 'that'}' files. Try one of: {allowed}.")
    if answers_question_id is not None and not db.question_exists(answers_question_id):
        raise HTTPException(404, "That question doesn't exist.")

    # The stored name comes from a random id, then the story's id: never from the uploaded filename.
    incoming = settings.data_dir / "audio" / f"incoming-{uuid.uuid4().hex}{ext}"
    try:
        size = 0
        with incoming.open("wb") as out:
            while chunk := await file.read(CHUNK_BYTES):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, "That recording is too large (the limit is 200 MB).")
                out.write(chunk)
        if size == 0:
            raise HTTPException(400, "That file is empty.")
        try:
            duration = await run_in_threadpool(audio.probe, incoming)
        except AudioError as exc:
            raise HTTPException(415, str(exc)) from None
    except Exception:
        incoming.unlink(missing_ok=True)
        raise

    story_id = db.create_story(answers_question_id, language_choice=language)
    relative = f"audio/{story_id}_original{ext}"
    incoming.replace(settings.data_dir / relative)
    db.update_story(story_id, audio_original=relative, duration_s=duration)
    background.add_task(pipeline.process_story, story_id)
    return {"id": story_id}


@router.get("")
def list_stories() -> list[dict]:
    return db.list_stories()


@router.get("/{story_id}")
def get_story(story_id: int) -> dict:
    story = _story_or_404(story_id)
    if story["status"] in db.IN_PROGRESS:
        story["estimate_s"] = pipeline.estimate(story)
    return story


Transcript = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100_000)]


class StoryEdit(BaseModel):
    title: Title | None = None
    transcript: Transcript | None = None
    mood: Mood | None = None


@router.patch("/{story_id}")
def edit_story(story_id: int, edit: StoryEdit) -> dict:
    """Rename a story, change its mood, or correct its transcript. Whisper's original words are kept."""
    story = _idle_story_or_409(story_id)
    changes = {}
    if edit.title is not None:
        changes["title"] = edit.title
    if edit.mood is not None:
        changes["mood"] = edit.mood
    if edit.transcript is not None and edit.transcript != story["transcript"]:
        changes["transcript"] = edit.transcript
        if story["transcript_original"] is None:
            changes["transcript_original"] = story["transcript"]
    if changes:
        db.update_story(story_id, **changes)
    return db.get_story(story_id)


@router.post("/{story_id}/reread", status_code=202)
def reread_story(story_id: int, background: BackgroundTasks) -> dict:
    """Let Gemma read the (corrected) words again: new title, summary, tags, questions and note.

    The recording and the retelling are kept; answered questions keep their answers. Words a person
    corrected are not put through the quality check again.
    """
    story = _idle_story_or_409(story_id)
    if not story["transcript"]:
        raise HTTPException(409, "There are no words to re-read yet.")
    db.update_story(story_id, status="queued", error=None, error_kind=None, reaction=None, started_at=None)
    background.add_task(pipeline.process_story, story_id)
    return {"id": story_id}


class Relisten(BaseModel):
    language: Language = "auto"


@router.post("/{story_id}/relisten", status_code=202)
def relisten_story(story_id: int, req: Relisten, background: BackgroundTasks) -> dict:
    """Transcribe the recording again, in the chosen language, then read the new words."""
    story = _idle_story_or_409(story_id)
    if not story["audio_original"]:
        raise HTTPException(409, "This story has no recording to listen to again.")
    db.clear_reading(story_id)
    db.update_story(story_id, status="queued", error=None, error_kind=None, transcript=None,
                    transcript_original=None, quality=None, language_probability=None, retelling=None,
                    language_choice=req.language, started_at=None)
    background.add_task(pipeline.process_story, story_id)
    return {"id": story_id}


@router.delete("/{story_id}", status_code=204)
def delete_story(story_id: int) -> Response:
    """Delete a story with everything added to it. It can be restored for a few seconds (trash.py)."""
    _idle_story_or_409(story_id)
    trash.delete(story_id)
    return Response(status_code=204)


@router.post("/{story_id}/restore")
def restore_story(story_id: int) -> dict:
    """Undo a delete, if it hasn't been carried out yet."""
    if not trash.restore(story_id):
        raise HTTPException(410, "Too late: that memory has already been laid to rest.")
    return db.get_story(story_id)


TagValue = Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)]


class TagEdit(BaseModel):
    kind: Literal["person", "place", "era", "keepsake"]
    old: str = Field("", max_length=200)  # "" adds `new` as a new tag
    new: TagValue = ""  # "" removes the tag


@router.post("/{story_id}/tags")
def edit_tag(story_id: int, edit: TagEdit) -> dict:
    """Add, rename, merge or remove one of this story's tags (other stories are not touched)."""
    _idle_story_or_409(story_id)
    db.rename_tag(story_id, edit.kind, edit.old, edit.new)
    return db.get_story(story_id)


@router.get("/{story_id}/audio")
def story_audio(story_id: int) -> FileResponse:
    """The original recording, exactly as it was given."""
    story = _story_or_404(story_id)
    path = settings.data_dir / (story["audio_original"] or "")
    if not story["audio_original"] or not path.is_file():
        raise HTTPException(404, "This story's recording is missing.")
    return FileResponse(path)


@router.post("/{story_id}/retry", status_code=202)
def retry_story(story_id: int, background: BackgroundTasks) -> dict:
    """Run the missing steps again after a passing problem (e.g. after starting Ollama)."""
    story = _story_or_404(story_id)
    if story["status"] != "failed":
        raise HTTPException(409, "Only failed stories can be retried.")
    if story["error_kind"] == "audio":
        raise HTTPException(409, "Trying this recording again won't help. Choose another file.")
    db.update_story(story_id, status="queued", error=None, error_kind=None, started_at=None)
    background.add_task(pipeline.process_story, story_id)
    return {"id": story_id}


@router.post("/{story_id}/visit", status_code=204)
def visit_story(story_id: int) -> None:
    """Opening a story relights its candle on the wall."""
    _story_or_404(story_id)
    db.update_story(story_id, last_visited_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))


@router.post("/{story_id}/reaction")
def story_reaction(story_id: int) -> StreamingResponse:
    """The Archivist's first words about a story: written live by Gemma once, then remembered."""
    story = _ready_story_or_409(story_id)
    return stream(_write_once(story, "reaction", prompts.reaction_messages(story), temperature=0.8))


@router.post("/{story_id}/retelling")
def story_retelling(story_id: int, again: bool = False) -> StreamingResponse:
    """The memory retold as a campfire ghost story. Stored apart: the original is never changed.

    `again=true` tells it anew; the old retelling is replaced only once the new one is complete.
    """
    story = _ready_story_or_409(story_id)
    return stream(_write_once(story, "retelling", prompts.retelling_messages(story), temperature=0.9, again=again))


def _write_once(story: dict, column: str, messages: list[dict], temperature: float,
                again: bool = False) -> Iterator[str]:
    """Stream Gemma's text into `column` the first time; afterwards replay what was kept."""
    if story[column] and not again:
        yield sse("token", {"text": story[column]})
        yield sse("done", {})
        return
    pieces = []
    try:
        for piece in llm.stream_chat(messages, temperature=temperature):
            pieces.append(piece)
            yield sse("token", {"text": piece})
    except LLMError as exc:
        yield sse("error", {"message": str(exc)})
        return
    text = "".join(pieces).strip()
    db.update_story(story["id"], **{column: text})
    threading.Thread(target=tts.prepare, args=(text,), daemon=True).start()  # voice it before it's asked for
    yield sse("done", {})


def _idle_story_or_409(story_id: int) -> dict:
    """A story that no background job is working on, so it is safe to change."""
    story = _story_or_404(story_id)
    if story["status"] in db.IN_PROGRESS:
        raise HTTPException(409, "The ghost is still working on this one. Try again when it has finished.")
    return story


def _ready_story_or_409(story_id: int) -> dict:
    story = _story_or_404(story_id)
    if story["status"] != "ready":
        raise HTTPException(409, "The ghost hasn't finished reading this one yet.")
    return story


def _story_or_404(story_id: int) -> dict:
    story = db.get_story(story_id)
    if story is None:
        raise HTTPException(404, "That memory was never given to me.")
    return story
