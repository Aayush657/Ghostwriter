"""The story pipeline: original audio -> 16 kHz WAV -> transcript -> quality check -> Gemma's analysis
-> the Archivist's note -> database.

Jobs run one at a time, so Whisper and Gemma never fight over RAM. Each step saves its
result before the next one starts: a failure never loses earlier work, and a retry
picks up from the first missing step.

A transcript Whisper was unsure of stops at the quality check with status "unclear": Gemma is not
asked to make a memory out of fog. The storyteller can listen again in another language, correct
the words by hand (which skips the check: a person wrote them), or delete it.
"""

from __future__ import annotations

import json
import logging
import statistics
import threading
import time
from datetime import datetime, timezone

from ghostwriter import db, embed, llm, transcribe, tts
from ghostwriter.audio import AudioError, normalise
from ghostwriter.config import settings
from ghostwriter.llm import LLMError, UnclearStory
from ghostwriter.transcribe import TranscribeError

log = logging.getLogger(__name__)

_one_at_a_time = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def process_story(story_id: int) -> None:
    """Run every missing step for one story. Never raises: failures are stored on the story."""
    with _one_at_a_time:
        try:
            _run(story_id)
        except (AudioError, TranscribeError) as exc:  # trying the same file again won't help
            db.update_story(story_id, status="failed", error=str(exc), error_kind="audio")
        except LLMError as exc:  # Ollama down, out of memory, a bad reply: worth another try
            db.update_story(story_id, status="failed", error=str(exc), error_kind="transient")
        except Exception:  # a story must never stay stuck in "processing"
            log.exception("story %s failed unexpectedly", story_id)
            db.update_story(story_id, status="failed", error_kind="transient",
                            error="Something went wrong while reading this story. Try again.")


def _run(story_id: int) -> None:
    story = db.get_story(story_id)
    if story is None:  # deleted while it waited its turn
        return
    data_dir = settings.data_dir
    db.update_story(story_id, started_at=_now())

    if not story["transcript"]:  # text-only stories (the samples) skip both audio steps
        db.update_story(story_id, status="transcribing", stage_at=_now(), error=None, error_kind=None)
        if not story["audio_wav"]:
            wav = f"audio/{story_id}.wav"
            duration = normalise(data_dir / story["audio_original"], data_dir / wav)
            db.update_story(story_id, audio_wav=wav, duration_s=duration)
            story = db.get_story(story_id)
        result = transcribe.transcribe(data_dir / story["audio_wav"], story["language_choice"], db.known_names())
        log.info("story %s: %.1fs of audio transcribed in %.1fs (%s, %s)", story_id, story["duration_s"],
                 result.seconds_taken, result.language, result.quality.reasons or "clear")
        db.record_timing("transcribing", result.seconds_taken, story["duration_s"])
        db.update_story(story_id, transcript=result.text, language=result.language,
                        language_probability=result.language_probability,
                        quality=json.dumps(result.quality_dict(), ensure_ascii=False))
        if result.quality.unclear:
            db.clear_reading(story_id)
            db.update_story(story_id, status="unclear")
            return
        story = db.get_story(story_id)

    db.update_story(story_id, status="thinking", stage_at=_now(), error=None, error_kind=None)
    answering = story.get("answers")
    started = time.perf_counter()
    try:
        analysis = llm.analyse_story(story["transcript"], answering)
    except UnclearStory:
        log.info("story %s: Gemma could only describe the words, not a memory", story_id)
        db.clear_reading(story_id)
        db.update_story(story_id, status="unclear")
        return
    analysis.unfinished_business = llm.unanswered_questions(story["transcript"], analysis, answering)
    db.record_timing("thinking", time.perf_counter() - started)
    db.save_analysis(story_id, analysis, status="noting" if not answering else "ready")
    db.update_story(story_id, stage_at=_now())
    threading.Thread(target=embed.refresh_quietly, daemon=True).start()  # for the Seance's meaning search
    if answering:  # an answer is shown inside its story; it needs no note of its own
        return

    # The Archivist's note is written now, so opening the story never waits for it.
    story = db.get_story(story_id)
    if not story["reaction"]:
        started = time.perf_counter()
        try:
            db.update_story(story_id, reaction=llm.write_note(story))
            db.record_timing("noting", time.perf_counter() - started)
        except LLMError as exc:  # the story is still complete; the page writes the note when opened
            log.warning("story %s: note not written: %s", story_id, exc)
    db.update_story(story_id, status="ready")
    if note := db.get_story(story_id)["reaction"]:
        threading.Thread(target=tts.prepare, args=(note,), daemon=True).start()  # voice it ahead of time


def _typical(step: str, audio_s: float | None) -> float | None:
    """How long `step` usually takes here (the median of recent runs), scaled by length for audio."""
    runs = db.timings(step)
    if not runs:
        return None
    if step == "transcribing":
        rates = [seconds / a for a, seconds in runs if a]
        return statistics.median(rates) * (audio_s or 60) if rates else None
    return statistics.median(seconds for _, seconds in runs)


def estimate(story: dict) -> float | None:
    """Seconds this story still needs, from what each step took on this computer before; None if unknown."""
    steps = ["transcribing", "thinking", "noting"]
    if story.get("answers_question_id"):
        steps.remove("noting")
    if story["status"] == "queued":
        if story["transcript"]:
            steps.remove("transcribing")
    elif story["status"] in steps:
        steps = steps[steps.index(story["status"]):]
    else:
        return None
    guesses = [_typical(step, story.get("duration_s")) for step in steps]
    if None in guesses:
        return None
    if story["status"] != "queued" and story.get("stage_at"):  # part of the current step is already done
        began = datetime.fromisoformat(story["stage_at"]).replace(tzinfo=timezone.utc)
        guesses[0] = max(0.0, guesses[0] - (datetime.now(timezone.utc) - began).total_seconds())
    return round(sum(guesses))
