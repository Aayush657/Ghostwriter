"""The story pipeline: original audio -> 16 kHz WAV -> transcript -> Gemma's analysis -> the
Archivist's note -> database.

Jobs run one at a time, so Whisper and Gemma never fight over RAM. Each step saves its
result before the next one starts: a failure never loses earlier work, and a retry
picks up from the first missing step.
"""

from __future__ import annotations

import logging
import threading

from ghostwriter import db, llm, transcribe
from ghostwriter.audio import AudioError, normalise
from ghostwriter.config import settings
from ghostwriter.llm import LLMError
from ghostwriter.transcribe import TranscribeError

log = logging.getLogger(__name__)

_one_at_a_time = threading.Lock()


def process_story(story_id: int) -> None:
    """Run every missing step for one story. Never raises: failures are stored on the story."""
    with _one_at_a_time:
        try:
            _run(story_id)
        except (AudioError, TranscribeError, LLMError) as exc:
            db.update_story(story_id, status="failed", error=str(exc))
        except Exception as exc:  # a story must never stay stuck in "processing"
            log.exception("story %s failed unexpectedly", story_id)
            db.update_story(story_id, status="failed", error=f"Unexpected error: {exc}")


def _run(story_id: int) -> None:
    story = db.get_story(story_id)
    data_dir = settings.data_dir

    if not story["transcript"]:  # text-only stories (the samples) skip both audio steps
        db.update_story(story_id, status="transcribing", error=None)
        if not story["audio_wav"]:
            wav = f"audio/{story_id}.wav"
            duration = normalise(data_dir / story["audio_original"], data_dir / wav)
            db.update_story(story_id, audio_wav=wav, duration_s=duration)
            story = db.get_story(story_id)
        result = transcribe.transcribe(data_dir / story["audio_wav"])
        log.info("story %s: %.1fs of audio transcribed in %.1fs (%s)", story_id,
                 story["duration_s"], result.seconds_taken, result.language)
        db.update_story(story_id, transcript=result.text, language=result.language)
        story = db.get_story(story_id)

    db.update_story(story_id, status="thinking", error=None)
    answering = story["answers"]["text"] if story.get("answers") else None
    analysis = llm.analyse_story(story["transcript"], answering)
    db.save_analysis(story_id, analysis, status="noting")

    # The Archivist's note is written now, so opening the story never waits for it.
    story = db.get_story(story_id)
    if not story["reaction"]:
        try:
            db.update_story(story_id, reaction=llm.write_note(story))
        except LLMError as exc:  # the story is still complete; the page writes the note when opened
            log.warning("story %s: note not written: %s", story_id, exc)
    db.update_story(story_id, status="ready")
