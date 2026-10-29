from types import SimpleNamespace

import pytest

from ghostwriter import transcribe
from ghostwriter.config import settings


class FakeWhisper:
    def __init__(self):
        self.language = "unset"

    def transcribe(self, path, vad_filter, beam_size, language):
        if language == "xx":
            raise ValueError("'xx' is not a valid language code")
        self.language = language
        return [SimpleNamespace(text=" Namaste ")], SimpleNamespace(language=language or "hi", language_probability=1.0)


@pytest.fixture
def whisper(monkeypatch):
    fake = FakeWhisper()
    monkeypatch.setattr(transcribe, "_model", lambda: fake)
    return fake


@pytest.mark.parametrize(("setting", "sent"), [("", None), (" HI ", "hi")])
def test_language_setting_reaches_whisper(whisper, monkeypatch, setting, sent):
    monkeypatch.setattr(settings, "whisper_language", setting)
    assert transcribe.transcribe("a.wav").text == "Namaste"
    assert whisper.language == sent


def test_unknown_language_code_is_explained(whisper, monkeypatch):
    monkeypatch.setattr(settings, "whisper_language", "xx")
    with pytest.raises(transcribe.TranscribeError, match="GW_WHISPER_LANGUAGE"):
        transcribe.transcribe("a.wav")
