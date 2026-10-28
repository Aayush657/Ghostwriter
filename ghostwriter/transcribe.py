"""Speech to text with faster-whisper. Fully offline: weights load from models/whisper/<size>/.

Benchmark a file from the command line:
    python -m ghostwriter.transcribe path\\to\\audio.wav
"""

from __future__ import annotations

import functools
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from ghostwriter.config import settings


class TranscribeError(Exception):
    """Whisper is unavailable or heard nothing. The message is safe to show the user."""


@dataclass
class Transcript:
    text: str
    language: str  # ISO code Whisper detected, e.g. "hi" or "en"
    language_probability: float
    seconds_taken: float


@functools.cache
def _model():
    """Load Whisper once, on first use (a few seconds), then keep it in memory.

    The pipeline runs one job at a time, so this is never loaded twice concurrently.
    """
    if not (settings.whisper_path / "model.bin").exists():
        raise TranscribeError(f"Whisper weights are missing from {settings.whisper_path}. Run scripts\\setup.ps1.")
    from faster_whisper import WhisperModel  # heavy import, deferred until needed

    return WhisperModel(str(settings.whisper_path), device="cpu", compute_type=settings.whisper_compute_type)


def transcribe(wav: Path) -> Transcript:
    """Transcribe a 16 kHz mono WAV. The language (Hindi, English, ...) is auto-detected."""
    start = time.perf_counter()
    # vad_filter skips long silences, which speeds things up and avoids Whisper "hallucinating" text.
    segments, info = _model().transcribe(str(wav), vad_filter=True, beam_size=5)
    text = " ".join(seg.text.strip() for seg in segments).strip()  # decoding happens in this loop
    if not text:
        raise TranscribeError("Only silence was heard in this recording.")
    return Transcript(text, info.language, info.language_probability, time.perf_counter() - start)


if __name__ == "__main__":
    import wave

    path = Path(sys.argv[1])
    with wave.open(str(path), "rb") as w:
        audio_s = w.getnframes() / w.getframerate()
    load_start = time.perf_counter()
    _model()
    print(f"model {settings.whisper_model}/{settings.whisper_compute_type} loaded in {time.perf_counter() - load_start:.1f}s")
    t = transcribe(path)
    print(f"language {t.language} (p={t.language_probability:.2f}), audio {audio_s:.1f}s, "
          f"took {t.seconds_taken:.1f}s = {t.seconds_taken / audio_s * 60:.1f}s per minute of audio")
    print(t.text)
