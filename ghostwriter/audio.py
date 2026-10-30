"""Audio handling with ffmpeg: check an upload really is audio, then turn it into the 16 kHz mono WAV
that Whisper expects, lightly cleaned up. Raw tool errors go to the server log; people see plain messages."""

from __future__ import annotations

import json
import logging
import subprocess
import wave
from pathlib import Path

from ghostwriter.config import settings

ALLOWED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".webm", ".ogg"}
MIN_SECONDS = 0.5
PLAYBACK_TYPES = {".wav": "audio/wav", ".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".webm": "audio/webm",
                  ".ogg": "audio/ogg"}  # not video/webm, which is what a guess by extension gives
# For Whisper's copy only (the original is kept for playback): cut rumble and hiss outside the voice,
# gently reduce steady noise, and even out the volume. On the test clips in PROGRESS.md (Listening)
# this took small.en from 9.8% to 9.3% of words wrong; levelling alone, or stronger settings, did worse.
CLEAN_UP = "highpass=f=80,lowpass=f=7600,afftdn=nr=10:nf=-40,dynaudnorm=f=200:g=15:p=0.9"

log = logging.getLogger(__name__)


class AudioError(Exception):
    """A recording could not be read or converted. The message is safe to show the user."""


def probe(path: Path) -> float | None:
    """Check that `path` holds playable audio of an acceptable length, before anything is saved.

    Returns the duration in seconds, or None when the file doesn't say (browser recordings often don't).
    """
    cmd = [settings.ffprobe, "-v", "error", "-select_streams", "a:0", "-show_entries",
           "stream=codec_type:format=duration", "-of", "json", str(path)]
    try:
        out = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=60).stdout
    except FileNotFoundError:
        log.warning("ffprobe not found at %s; uploads are checked when they are converted", settings.ffprobe)
        return None
    except subprocess.TimeoutExpired:
        raise AudioError("That file took too long to open. Try another recording.") from None
    except subprocess.CalledProcessError as exc:
        log.info("ffprobe refused %s: %s", path.name, exc.stderr.strip()[-300:])
        raise AudioError("That file isn't a recording. Choose an audio file "
                         "(wav, mp3, m4a, webm or ogg).") from None
    info = json.loads(out or "{}")
    if not info.get("streams"):
        raise AudioError("That file has no sound in it. Choose an audio recording.")
    duration = info.get("format", {}).get("duration")
    seconds = float(duration) if duration not in (None, "N/A") else None
    if seconds is not None and seconds < MIN_SECONDS:
        raise AudioError("That recording is too short to hold a story.")
    if seconds is not None and seconds > settings.max_audio_minutes * 60:
        raise AudioError(f"That recording is longer than {settings.max_audio_minutes} minutes. "
                         "Split it into shorter stories.")
    return seconds


def playback_copy(original: Path) -> Path:
    return original.with_name(original.stem.replace("_original", "_play") + original.suffix)


def playable(original: Path) -> Path:
    """The file to play. Browser recordings (webm) carry no duration, so players show 0:00 and can't
    seek; ffmpeg copies the sound into a new file (no re-encoding) that has both. The original stays
    exactly as it was given. Made once, on save or on the first play; the original if ffmpeg fails."""
    if original.suffix.lower() != ".webm":
        return original
    copy = playback_copy(original)
    if not copy.exists():
        part = copy.with_name(f"{copy.stem}.part{copy.suffix}")
        try:
            subprocess.run([settings.ffmpeg_bin, "-y", "-loglevel", "error", "-i", str(original), "-c", "copy",
                            str(part)], check=True, capture_output=True, timeout=120)
            part.replace(copy)
        except (OSError, subprocess.SubprocessError) as exc:
            log.warning("could not make a seekable copy of %s: %s", original.name, exc)
            part.unlink(missing_ok=True)
            return original
    return copy


def normalise(src: Path, dst: Path) -> float:
    """Write `src` as 16 kHz mono 16-bit WAV to `dst` and return its duration in seconds.

    The original file is never touched; it stays for playback.
    """
    cmd = [settings.ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error", "-i", str(src),
           "-af", CLEAN_UP, "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(dst)]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=600)
    except FileNotFoundError:
        raise AudioError("ffmpeg is not installed (or GW_FFMPEG_BIN points to the wrong place).") from None
    except subprocess.TimeoutExpired:
        raise AudioError("ffmpeg took more than 10 minutes on this file.") from None
    except subprocess.CalledProcessError as exc:
        log.warning("ffmpeg could not convert %s: %s", src.name, exc.stderr.strip()[-300:])
        raise AudioError("This file could not be read as audio. Choose another recording.") from None
    with wave.open(str(dst), "rb") as w:
        seconds = w.getnframes() / w.getframerate()
    if seconds > settings.max_audio_minutes * 60:
        raise AudioError(f"That recording is longer than {settings.max_audio_minutes} minutes. "
                         "Split it into shorter stories.")
    return seconds
