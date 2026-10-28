"""Audio tests against the real ffmpeg (skipped if ffmpeg isn't installed)."""

import shutil
import subprocess

import pytest

from ghostwriter import audio
from ghostwriter.config import settings

needs_ffmpeg = pytest.mark.skipif(shutil.which(settings.ffmpeg_bin) is None, reason="ffmpeg not installed")


@needs_ffmpeg
def test_normalise_makes_16k_mono_wav(tmp_path):
    src = tmp_path / "tone.mp3"
    subprocess.run([settings.ffmpeg_bin, "-loglevel", "error", "-f", "lavfi", "-i",
                    "sine=frequency=440:duration=2", "-ac", "2", "-ar", "44100", str(src)], check=True)
    dst = tmp_path / "tone.wav"

    duration = audio.normalise(src, dst)

    import wave
    with wave.open(str(dst), "rb") as w:
        assert (w.getnchannels(), w.getframerate(), w.getsampwidth()) == (1, 16000, 2)
    assert abs(duration - 2.0) < 0.1


@needs_ffmpeg
def test_garbage_file_gives_a_friendly_error(tmp_path):
    src = tmp_path / "not-audio.mp3"
    src.write_bytes(b"this is not audio")
    with pytest.raises(audio.AudioError, match="could not be read as audio"):
        audio.normalise(src, tmp_path / "out.wav")
