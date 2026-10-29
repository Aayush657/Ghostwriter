"""Speech to text with faster-whisper. Fully offline: weights load from models/whisper/<size>/.

Benchmark a file from the command line:
    python -m ghostwriter.transcribe path\\to\\audio.wav [auto|en|hi|hinglish]
"""

from __future__ import annotations

import functools
import sys
import time
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ghostwriter.config import settings


class TranscribeError(Exception):
    """Whisper is unavailable or heard nothing. The message is safe to show the user."""


# What the storyteller can choose next to the record button, and what Whisper is told for each.
# Hinglish is Hindi with English words kept in Latin script; the example sentence below shows Whisper how.
LANGUAGE_CHOICES = {"auto": None, "en": "en", "hi": "hi", "hinglish": "hi"}
MIXED_EXAMPLE = "मैं school से आता था, फिर हम market गए। Nani की kitchen में chai बनती थी।"

# Words Whisper's small model often mishears in Indian family stories ("Mira", "Puna", "armourer").
# Names already in the archive go first; together they form the prompt Whisper reads before listening.
FAMILY_WORDS = ["Nani", "Nana", "Dadi", "Dada", "Mama", "Mami", "Chacha", "Chachi", "Bua", "Mausi", "Didi",
                "Bhaiya", "almirah", "kadhi", "paratha", "diya", "haveli", "verandah"]
CITIES = ["Lucknow", "Pune", "Jaipur", "Shimla", "Delhi", "Mumbai", "Kolkata", "Chennai", "Allahabad", "Varanasi"]
MAX_PROMPT_CHARS = 600  # Whisper reads at most ~224 prompt tokens


def glossary(names: list[str] = ()) -> str:
    words = list(dict.fromkeys(n.split(" (")[0].strip() for n in [*names, *FAMILY_WORDS, *CITIES] if n.strip()))
    text = "Glossary: "
    for word in words:
        if len(text) + len(word) + 2 > MAX_PROMPT_CHARS:
            break
        text += word + ", "
    return text.rstrip(", ") + "."


@dataclass
class Quality:
    """How sure Whisper was. Low confidence means the words may be fog, not a memory."""

    avg_logprob: float          # mean log-probability of the words (0 is certain; below -1 is a guess)
    no_speech_prob: float       # the highest chance that a stretch was not speech at all
    compression_ratio: float    # high when the same words repeat in a loop (a known Whisper failure)
    language_probability: float
    low_ratio: float            # share of words Whisper gave less than even odds
    low_words: list[str] = field(default_factory=list)
    scripts: list[str] = field(default_factory=list)  # alphabets in the text: LATIN, DEVANAGARI, ...
    reasons: list[str] = field(default_factory=list)  # why it was judged unclear; empty when clear

    @property
    def unclear(self) -> bool:
        return bool(self.reasons)


@dataclass
class Transcript:
    text: str
    language: str  # ISO code Whisper used or detected, e.g. "hi" or "en"
    language_probability: float
    seconds_taken: float
    quality: Quality

    def quality_dict(self) -> dict:
        return asdict(self.quality)


def scripts(text: str) -> list[str]:
    """The alphabets letters in `text` come from, e.g. ['DEVANAGARI', 'LATIN']."""
    return sorted({unicodedata.name(ch, "?").split()[0] for ch in text if ch.isalpha()})


def judge(q: Quality, detected: bool) -> list[str]:
    """Reasons to distrust a transcript. Thresholds were set on real recordings (PROGRESS.md, Measurements):
    clear speech scores around -0.3 with almost no unsure words; a noisy room recording heard as the
    wrong language scored -0.67 with 29% unsure words, and failed all four weak signs at once."""
    reasons = []
    if q.avg_logprob < -0.8:
        reasons.append("Whisper was guessing at most of the words")
    if q.compression_ratio > 2.4:  # Whisper's own threshold for a repetition loop
        reasons.append("the same words repeat in a loop")
    if len(q.scripts) >= 3:
        reasons.append("the words came out in several alphabets at once")
    weak = [q.avg_logprob < -0.55, q.low_ratio > 0.2, detected and q.language_probability < 0.6,
            q.no_speech_prob > 0.45]
    if sum(weak) >= 2:
        reasons.append("much of it sounded like noise or an unknown language")
    return reasons


@functools.cache
def _model():
    """Load Whisper once, on first use (a few seconds), then keep it in memory.

    The pipeline runs one job at a time, so this is never loaded twice concurrently.
    """
    if not (settings.whisper_path / "model.bin").exists():
        raise TranscribeError(f"Whisper weights are missing from models/whisper/{settings.whisper_model}. "
                              "Run scripts\\setup.ps1.")
    from faster_whisper import WhisperModel  # heavy import, deferred until needed

    return WhisperModel(str(settings.whisper_path), device="cpu", compute_type=settings.whisper_compute_type)


def warm_up() -> None:
    """Load the weights ahead of the first recording. Never raises."""
    try:
        _model()
    except Exception:  # a missing model is already reported by the health check
        pass


def transcribe(wav: Path, choice: str | None = "auto", names: list[str] = ()) -> Transcript:
    """Transcribe a 16 kHz mono WAV in the chosen language (auto-detected unless chosen or set in .env)."""
    start = time.perf_counter()
    language = LANGUAGE_CHOICES.get(choice or "auto") or settings.whisper_language.strip().lower() or None
    prompt = glossary(names)
    if choice == "hinglish":
        prompt = f"{MIXED_EXAMPLE} {prompt}"
    try:
        # vad_filter skips long silences, which speeds things up and avoids Whisper "hallucinating" text;
        # word_timestamps gives each word its own probability, for the quality check.
        segments, info = _model().transcribe(str(wav), vad_filter=True, beam_size=5, language=language,
                                             initial_prompt=prompt, word_timestamps=True)
        segments = list(segments)  # decoding happens here
    except ValueError:  # faster-whisper rejects unknown language codes
        raise TranscribeError(f"Whisper doesn't know the language code \"{language}\" "
                              "(GW_WHISPER_LANGUAGE in .env). Use one like hi or en, or leave it empty.") from None
    text = " ".join(seg.text.strip() for seg in segments).strip()
    if not text:
        raise TranscribeError("Only silence was heard in this recording.")

    spoken = sum(s.end - s.start for s in segments) or 1.0
    words = [w for s in segments for w in (s.words or [])]
    unsure = [w.word.strip() for w in words if w.probability < 0.5]
    quality = Quality(
        avg_logprob=round(sum(s.avg_logprob * (s.end - s.start) for s in segments) / spoken, 3),
        no_speech_prob=round(max(s.no_speech_prob for s in segments), 3),
        compression_ratio=round(max(s.compression_ratio for s in segments), 3),
        language_probability=round(info.language_probability, 3),
        low_ratio=round(len(unsure) / max(1, len(words)), 3),
        low_words=list(dict.fromkeys(unsure))[:20],
        scripts=scripts(text),
    )
    quality.reasons = judge(quality, detected=language is None)
    return Transcript(text, info.language, info.language_probability, time.perf_counter() - start, quality)


if __name__ == "__main__":
    import wave

    path = Path(sys.argv[1])
    with wave.open(str(path), "rb") as w:
        audio_s = w.getnframes() / w.getframerate()
    load_start = time.perf_counter()
    _model()
    print(f"model {settings.whisper_model}/{settings.whisper_compute_type} loaded in {time.perf_counter() - load_start:.1f}s")
    t = transcribe(path, sys.argv[2] if len(sys.argv) > 2 else "auto")
    print(f"language {t.language} (p={t.language_probability:.2f}), audio {audio_s:.1f}s, "
          f"took {t.seconds_taken:.1f}s = {t.seconds_taken / audio_s * 60:.1f}s per minute of audio")
    print(f"quality: {t.quality}")
    print(t.text)
