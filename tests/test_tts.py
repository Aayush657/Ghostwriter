"""Ghost voice tests. The real-synthesis test runs only where Piper and the voice are installed."""

import shutil
import wave

import pytest
from fastapi.testclient import TestClient

from ghostwriter import tts
from ghostwriter.api import main
from ghostwriter.config import settings

has_piper = shutil.which(settings.piper_bin) is not None and settings.piper_voice_path.exists()


def test_citations_are_not_read_aloud():
    assert tts.clean("Your grandmother made kadhi [S3].\n It was famous [S3] [S12, S4].") == \
        "Your grandmother made kadhi. It was famous."


def test_text_is_spoken_first_sentence_first():
    text = "Ah, a memory of rain [S3]. The roof leaked. " + "Your grandmother laughed and laughed. " * 12
    parts = tts.parts(text)
    assert parts[0] == "Ah, a memory of rain."  # short, so the voice starts at once
    assert all(len(p) <= tts.PART_CHARS for p in parts[1:])
    assert " ".join(parts) == tts.clean(text)  # nothing lost or repeated
    assert tts.parts("[S3]") == []


def test_turned_off_voice_explains_itself(monkeypatch):
    monkeypatch.setattr(settings, "tts_enabled", False)
    with pytest.raises(tts.TTSError, match="GW_TTS_ENABLED"):
        tts.speak("hello")


def test_missing_voice_model_explains_itself(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "models_dir", tmp_path)
    with pytest.raises(tts.TTSError, match="voice model is missing"):
        tts.speak("hello")


@pytest.mark.skipif(not has_piper, reason="Piper or its voice is not installed")
def test_real_voice_is_made_once_then_cached(data_dir):
    first = tts.speak("The archive is awake [S1].")
    with wave.open(str(first), "rb") as w:
        assert w.getnframes() / w.getframerate() > 1.0  # at least a second of speech
    mtime = first.stat().st_mtime_ns
    assert tts.speak("The archive is awake [S1].") == first
    assert first.stat().st_mtime_ns == mtime  # served from the cache, not made again


def test_speak_route_returns_a_friendly_503_when_voice_is_off(data_dir, monkeypatch):
    monkeypatch.setattr(settings, "tts_enabled", False)
    monkeypatch.setattr(main.selfcheck, "run_checks", lambda: [])
    with TestClient(main.app, base_url="http://127.0.0.1:8000") as client:
        resp = client.post("/api/speak", json={"text": "hello"})
    assert resp.status_code == 503
    assert "GW_TTS_ENABLED" in resp.json()["detail"]
