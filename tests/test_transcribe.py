"""Transcription tests with a fake Whisper: English only, the name glossary, and the quality gate.

The quality figures used here are the ones measured on real recordings (PROGRESS.md, Measurements).
"""

from types import SimpleNamespace

import pytest

from ghostwriter import transcribe


def segment(text, logprob=-0.3, no_speech=0.01, ratio=1.4, unsure=0):
    words = [SimpleNamespace(word=w, probability=0.3 if i < unsure else 0.95) for i, w in enumerate(text.split())]
    return SimpleNamespace(text=text, start=0.0, end=5.0, avg_logprob=logprob, no_speech_prob=no_speech,
                           compression_ratio=ratio, words=words)


class FakeWhisper:
    def __init__(self, segments=None):
        self.segments = segments or [segment(" My friend Maya and I snuck down to the dock at Pine Lake. ")]
        self.calls = []

    def transcribe(self, path, **kwargs):
        self.calls.append(kwargs)
        return iter(self.segments), SimpleNamespace(language="en", language_probability=1.0)


@pytest.fixture
def whisper(monkeypatch):
    fake = FakeWhisper()
    monkeypatch.setattr(transcribe, "_model", lambda: fake)
    return fake


def test_whisper_always_listens_in_english(whisper):
    assert transcribe.transcribe("a.wav").text == "My friend Maya and I snuck down to the dock at Pine Lake."
    call = whisper.calls[-1]
    assert call["language"] == "en"
    assert call["beam_size"] == 5 and call["vad_filter"] and call["word_timestamps"]


def test_names_already_in_the_archive_guide_whisper(whisper):
    transcribe.transcribe("a.wav", ["Maya (friend)", "Camp Wahkeena", "Maya"])
    assert whisper.calls[-1]["initial_prompt"] == "Glossary: Maya, Camp Wahkeena."


def test_no_names_means_no_prompt(whisper):
    transcribe.transcribe("a.wav")
    assert whisper.calls[-1]["initial_prompt"] is None  # nothing to bias Whisper towards


def test_a_long_glossary_is_cut_to_what_whisper_reads(whisper):
    transcribe.transcribe("a.wav", [f"Name{i}" for i in range(200)])
    prompt = whisper.calls[-1]["initial_prompt"]
    assert prompt.startswith("Glossary: Name0, Name1,") and len(prompt) <= transcribe.MAX_PROMPT_CHARS


def test_silence_is_explained(monkeypatch):
    monkeypatch.setattr(transcribe, "_model", lambda: FakeWhisper([segment("   ")]))
    with pytest.raises(transcribe.TranscribeError, match="silence"):
        transcribe.transcribe("a.wav")


def test_clear_speech_passes_the_quality_check(whisper):
    quality = transcribe.transcribe("a.wav").quality
    assert not quality.unclear
    assert quality.scripts == ["LATIN"] and quality.low_ratio == 0


def test_a_noisy_room_is_unclear(monkeypatch):
    # The real noisy recording (story 6): logprob -0.67, 29% unsure words, no-speech 0.50.
    words = "the lamp and the room is a open the door and the the lamp the go to it is"
    fake = FakeWhisper([segment(words, logprob=-0.67, no_speech=0.5, ratio=1.9, unsure=6)])
    monkeypatch.setattr(transcribe, "_model", lambda: fake)
    quality = transcribe.transcribe("a.wav").quality
    assert quality.unclear and "noise" in quality.reasons[0]
    assert quality.low_words[:2] == ["the", "lamp"]


def test_words_in_other_alphabets_are_unclear(monkeypatch):
    fake = FakeWhisper([segment("ते 그리고 and the memory of a lamp on the terrace")])
    monkeypatch.setattr(transcribe, "_model", lambda: fake)
    quality = transcribe.transcribe("a.wav").quality
    assert quality.scripts == ["DEVANAGARI", "HANGUL", "LATIN"]
    assert "other alphabets" in quality.reasons[0]


def test_a_repetition_loop_or_guessing_is_unclear(monkeypatch):
    loop = FakeWhisper([segment("the lamp the lamp the lamp the lamp", ratio=3.1)])
    monkeypatch.setattr(transcribe, "_model", lambda: loop)
    assert transcribe.transcribe("a.wav").quality.unclear
    guessing = FakeWhisper([segment("my cuss in mare of mare add bared", logprob=-1.7, unsure=5)])
    monkeypatch.setattr(transcribe, "_model", lambda: guessing)
    assert "guessing" in transcribe.transcribe("a.wav").quality.reasons[0]


def test_one_unsure_word_is_not_fog(monkeypatch):
    fake = FakeWhisper([segment("Old Hollis sat on the porch swing in Grandpa's red scarf", logprob=-0.4, unsure=1)])
    monkeypatch.setattr(transcribe, "_model", lambda: fake)
    assert not transcribe.transcribe("a.wav").quality.unclear
