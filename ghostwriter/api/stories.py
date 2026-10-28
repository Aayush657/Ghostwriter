"""Story routes: upload a recording, list the archive, read one story, play its audio, retry a failure."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from ghostwriter import db, llm, pipeline, prompts
from ghostwriter.api.sse import sse, stream
from ghostwriter.audio import ALLOWED_EXTENSIONS
from ghostwriter.config import settings
from ghostwriter.llm import LLMError

router = APIRouter(prefix="/api/stories", tags=["stories"])

MAX_UPLOAD_BYTES = 200 * 1024 * 1024
CHUNK_BYTES = 1024 * 1024


@router.post("", status_code=201)
async def upload_story(
    background: BackgroundTasks,
    file: UploadFile,
    answers_question_id: int | None = Form(None),
) -> dict:
    """Save the recording untouched, then transcribe and analyse it in the background."""
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise HTTPException(415, f"The ghost can't read '{ext or 'that'}' files. Try one of: {allowed}.")
    if answers_question_id is not None and not db.question_exists(answers_question_id):
        raise HTTPException(404, "That question doesn't exist.")

    story_id = db.create_story(answers_question_id)
    # The stored name comes from the id, never from the uploaded filename.
    relative = f"audio/{story_id}_original{ext}"
    dest = settings.data_dir / relative
    try:
        size = 0
        with dest.open("wb") as out:
            while chunk := await file.read(CHUNK_BYTES):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, "That recording is too large (the limit is 200 MB).")
                out.write(chunk)
        if size == 0:
            raise HTTPException(400, "That file is empty.")
    except Exception:
        dest.unlink(missing_ok=True)
        db.delete_story(story_id)
        raise
    db.update_story(story_id, audio_original=relative)
    background.add_task(pipeline.process_story, story_id)
    return {"id": story_id}


@router.get("")
def list_stories() -> list[dict]:
    return db.list_stories()


@router.get("/{story_id}")
def get_story(story_id: int) -> dict:
    return _story_or_404(story_id)


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
    """Run the missing steps again for a failed story (e.g. after starting Ollama)."""
    story = _story_or_404(story_id)
    if story["status"] != "failed":
        raise HTTPException(409, "Only failed stories can be retried.")
    db.update_story(story_id, status="queued", error=None)
    background.add_task(pipeline.process_story, story_id)
    return {"id": story_id}


@router.post("/{story_id}/reaction")
def story_reaction(story_id: int) -> StreamingResponse:
    """The Archivist's first words about a story: written live by Gemma once, then remembered."""
    story = _story_or_404(story_id)
    if story["status"] != "ready":
        raise HTTPException(409, "The ghost hasn't finished reading this one yet.")
    return stream(_reaction_events(story))


def _reaction_events(story: dict) -> Iterator[str]:
    if story["reaction"]:
        yield sse("token", {"text": story["reaction"]})
        yield sse("done", {})
        return
    pieces = []
    try:
        for piece in llm.stream_chat(prompts.reaction_messages(story), temperature=0.8):
            pieces.append(piece)
            yield sse("token", {"text": piece})
    except LLMError as exc:
        yield sse("error", {"message": str(exc)})
        return
    db.update_story(story["id"], reaction="".join(pieces).strip())
    yield sse("done", {})


def _story_or_404(story_id: int) -> dict:
    story = db.get_story(story_id)
    if story is None:
        raise HTTPException(404, "That memory was never given to me.")
    return story
