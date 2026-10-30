"""The Archivist's voice: Piper (offline neural text-to-speech) piped through ffmpeg ghost effects.

Piper runs as a separate program. Its raw audio streams straight into ffmpeg, which lowers the
pitch and adds an echoing stone room. Text is spoken in parts (the first sentence, then a few
sentences at a time), so the page can start playing the first part while the next is being made.
Each part is cached by its text, so it is made once; notes are voiced as soon as they are written.
It's optional: if Piper or the voice is missing, the app still works and just stays silent.

Try it:  python -m ghostwriter.tts "The archive is awake."
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

from ghostwriter.config import settings
from ghostwriter.whispers import SENTENCE_END

log = logging.getLogger(__name__)

# The Archivist's voice, as chosen in the voice lab (Cori; pitch 0.90x, pace 0.90x; echo 10% at
# 120 ms with 25% repeats; a 0.8 s stone room at 20%; low cut 60 Hz; warmth +4 dB; shimmer 6%).
# Piper slows the pace itself, which sounds cleaner than stretching the audio afterwards.
LENGTH_SCALE = 1 / 0.90
ROOM_SECONDS = 0.8
ROOM_GAIN = 25.0  # afir normalises the room ~38 dB under the voice; x25 restores the lab's 0.32 share
GHOST_GRAPH = (
    "[0:a]apad=pad_dur=0.4,rubberband=pitch=0.90,highpass=f=60,bass=g=4:f=250,"  # room for the echo's tail
    "chorus=1:1:22:0.06:0.8:4,asplit=2[voice][wall];"                             # the faint double voice
    "[voice]aecho=0.9:1:120|240|360:0.1|0.025|0.006[near];"                       # dry voice + echo repeats
    f"[wall][1:a]afir[room];[room]volume={ROOM_GAIN}[far];"                        # the stone room
    "[near][far]amix=inputs=2:normalize=0,alimiter=limit=0.9,"
    "loudnorm=I=-16:TP=-1.5:LRA=11,aresample=44100"                                # every part equally loud
)
MAX_CHARS = 3500  # about three and a half minutes of speech; fits a whole retelling (300-450 words)
PART_CHARS = 280  # later parts gather sentences up to about this length


class TTSError(Exception):
    """The voice couldn't be made. The message is safe to show the user."""


EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u200D]")


def clean(text: str) -> str:
    """Drop [S12] citation marks and emojis (neither is for reading aloud); squeeze whitespace onto one line."""
    text = EMOJI.sub("", re.sub(r"\s*\[S\d+(?:\s*,\s*S?\d+)*\]", "", text))
    return re.sub(r"\s+", " ", text).strip()


def parts(text: str) -> list[str]:
    """The pieces `text` is spoken in: the first sentence alone (so the voice starts quickly), then
    sentences gathered into parts of up to PART_CHARS."""
    sentences = [s for s in SENTENCE_END.split(clean(text)[:MAX_CHARS]) if s.strip()]
    if not sentences:
        return []
    out = [sentences[0]]
    for sentence in sentences[1:]:
        if len(out) > 1 and len(out[-1]) + len(sentence) < PART_CHARS:
            out[-1] += " " + sentence
        else:
            out.append(sentence)
    return out


def cache_paths(text: str) -> list[Path]:
    """Every file the spoken versions of `text` may be cached in (both voices, whole and in parts)."""
    return [cache_path(t, ghostly) for t in [text, *parts(text)] for ghostly in (True, False)]


def prepare(text: str) -> None:
    """Make the ghost voice for `text` ahead of time, so pressing play starts at once. Never raises."""
    if not settings.tts_enabled or not text:
        return
    try:
        for part in parts(text):
            speak(part)
    except TTSError as exc:
        log.info("voice not prepared: %s", exc)


def cache_path(text: str, ghostly: bool = True) -> Path:
    """Where the spoken version of `text` is (or would be) kept."""
    sound = GHOST_GRAPH if ghostly else "plain"  # changing the effects never replays old audio
    key = hashlib.sha256(f"{settings.piper_voice}|{LENGTH_SCALE}|{sound}|{clean(text)[:MAX_CHARS]}".encode()).hexdigest()[:24]
    return settings.data_dir / "tts" / f"{key}.wav"


def _room() -> Path:
    """The stone room's impulse response: fading noise, made once with ffmpeg and kept beside the cache."""
    path = settings.data_dir / "tts" / f"room-{ROOM_SECONDS}s.wav"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([settings.ffmpeg_bin, "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                        f"anoisesrc=d={ROOM_SECONDS}:c=white:r=22050:a=0.5:seed=7", "-af",
                        f"afade=t=out:st=0:d={ROOM_SECONDS}:curve=cub", "-ac", "1", str(path)],
                       check=True, capture_output=True, timeout=30)
    return path


def speak(text: str, ghostly: bool = True) -> Path:
    """Return a WAV file of `text` spoken by the Archivist, making it if it isn't cached yet."""
    if not settings.tts_enabled:
        raise TTSError("The voice is turned off (GW_TTS_ENABLED=false in .env).")
    text = clean(text)[:MAX_CHARS]
    if not text:
        raise TTSError("There is nothing to say.")
    voice = settings.piper_voice_path
    if not voice.exists():
        raise TTSError(f"The voice model is missing from {voice}. Run scripts\\setup.ps1.")

    out = cache_path(text, ghostly)
    if out.exists():
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    partial = out.with_name(f"{out.stem}.{uuid.uuid4().hex[:8]}.part.wav")  # unique: requests may overlap

    rate = json.loads(Path(f"{voice}.json").read_text(encoding="utf-8"))["audio"]["sample_rate"]
    try:
        piper = subprocess.Popen(
            [settings.piper_bin, "--model", str(voice), "--length_scale", f"{LENGTH_SCALE:.3f}",
             "--sentence_silence", "0.35", "--output_raw"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        raise TTSError("Piper isn't installed (or GW_PIPER_BIN points to the wrong place). "
                       "See README > Ghost voice.") from None
    try:
        ffmpeg = subprocess.Popen(
            [settings.ffmpeg_bin, "-y", "-loglevel", "error", "-f", "s16le", "-ar", str(rate), "-ac", "1",
             "-i", "pipe:0", *(["-i", str(_room()), "-filter_complex", GHOST_GRAPH] if ghostly else ["-af", "anull"]),
             str(partial)],
            stdin=piper.stdout, stderr=subprocess.PIPE, text=True,
        )
    except FileNotFoundError:
        piper.kill()
        raise TTSError("ffmpeg is not installed (or GW_FFMPEG_BIN points to the wrong place).") from None
    piper.stdout.close()  # ffmpeg now owns the pipe and sees end-of-file when Piper finishes
    try:
        piper.stdin.write(text.encode("utf-8"))
        piper.stdin.close()
        _, ffmpeg_errors = ffmpeg.communicate(timeout=120)
        piper.wait(timeout=10)
    except subprocess.TimeoutExpired:
        piper.kill()
        ffmpeg.kill()
        partial.unlink(missing_ok=True)
        raise TTSError("The voice took too long to form.") from None
    if piper.returncode or ffmpeg.returncode or not partial.exists():
        partial.unlink(missing_ok=True)
        raise TTSError(f"The voice failed to form ({(ffmpeg_errors or 'piper error').strip()[-200:]}).")
    partial.replace(out)
    return out


if __name__ == "__main__":
    start = time.perf_counter()
    path = speak(" ".join(sys.argv[1:]) or "The archive is awake, and it remembers you.")
    print(f"{path} in {time.perf_counter() - start:.2f}s")
