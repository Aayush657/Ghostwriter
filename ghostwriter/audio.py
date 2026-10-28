"""Audio handling with ffmpeg: turn any recording into the 16 kHz mono WAV that Whisper expects."""

from __future__ import annotations

import subprocess
import wave
from pathlib import Path

from ghostwriter.config import settings

ALLOWED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".webm", ".ogg"}


class AudioError(Exception):
    """A recording could not be read or converted. The message is safe to show the user."""


def normalise(src: Path, dst: Path) -> float:
    """Write `src` as 16 kHz mono 16-bit WAV to `dst` and return its duration in seconds.

    The original file is never touched; it stays for playback.
    """
    cmd = [settings.ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error", "-i", str(src),
           "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(dst)]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=600)
    except FileNotFoundError:
        raise AudioError("ffmpeg is not installed (or GW_FFMPEG_BIN points to the wrong place).") from None
    except subprocess.TimeoutExpired:
        raise AudioError("ffmpeg took more than 10 minutes on this file.") from None
    except subprocess.CalledProcessError as exc:
        reason = exc.stderr.strip().splitlines()[-1] if exc.stderr.strip() else "unknown error"
        raise AudioError(f"This file could not be read as audio ({reason}).") from exc
    with wave.open(str(dst), "rb") as w:
        return w.getnframes() / w.getframerate()
