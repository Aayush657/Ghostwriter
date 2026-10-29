"""Shared fixtures. Every test gets its own empty data folder, so real data is never touched."""

import io
import math
import struct
import wave

import pytest

from ghostwriter import db
from ghostwriter.config import settings
from ghostwriter.models import StoryAnalysis


def wav_bytes(seconds: float = 1.0, rate: int = 16000) -> bytes:
    """A real (if tuneless) recording: a quiet 220 Hz tone, so ffprobe accepts it as audio."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"".join(struct.pack("<h", int(3000 * math.sin(2 * math.pi * 220 * i / rate)))
                               for i in range(int(seconds * rate))))
    return buf.getvalue()


@pytest.fixture(autouse=True)
def no_background_work(monkeypatch):
    """Preparing the voice and meaning search run in background threads in the app; not in tests."""
    from ghostwriter import embed, trash, tts
    monkeypatch.setattr(tts, "prepare", lambda text: None)
    monkeypatch.setattr(embed, "refresh_quietly", lambda: None)
    monkeypatch.setattr(trash, "_schedule_purge", lambda: None)  # tests purge explicitly


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    db.init_db()
    return settings.data_dir


@pytest.fixture
def analysis():
    return StoryAnalysis(
        title="The Lamp on Dadi's Terrace",
        summary="Dadi lit a brass lamp every Diwali. One year it went out by itself.",
        people=["Dadi (grandmother)"],
        places=["Allahabad"],
        eras=["1990s"],
        mood="eerie",
        keepsakes=["brass lamp"],
        unfinished_business=["What happened to the brass lamp?", "Who was on the terrace that night?"],
    )
