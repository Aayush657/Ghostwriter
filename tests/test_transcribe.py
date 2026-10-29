"""Transcription tests with a fake Whisper: language choices, the name glossary, and the quality gate.

The quality figures used here are the ones measured on real recordings (PROGRESS.md, Measurements).
"""

from types import SimpleNamespace

import pytest

from ghostwriter import transcribe
from ghostwriter.config import settings


def segment(text, logprob=-0.3, no_speech=0.01, ratio=1.4, unsure=0):
    words = [SimpleNamespace(word=w, probability=0.3 if i < unsure else 0.95) for i, w in enumerate(text.split())]
    return SimpleNamespace(text=text, start=0.0, end=5.0, avg_logprob=logprob, no_speech_prob=no_speech,
                           compression_ratio=ratio, words=words)


class FakeWhisper:
    def __init__(self, segments=None, language_probability=0.99):
        self.segments = segments or [segment(" My cousin Meera and I buried a brass key in Pune. ")]
        self.language_probability = language_probability
        self.calls = []

    def transcribe(self, path, **kwargs):
        if kwargs["language"] == "xx":
            raise ValueError("'xx' is not a valid language code")
        self.calls.append(kwargs)
        return iter(self.segments), SimpleNamespace(language=kwargs["language"] or "en",
                                                    language_probability=self.language_probability)


@pytest.fixture
def whisper(monkeypatch):
    fake = FakeWhisper()
    monkeypatch.setattr(transcribe, "_model", lambda: fake)
    return fake


@pytest.mark.parametrize(("setting", "choice", "sent"), [("", "auto", None), (" HI ", "auto", "hi"),
                                                          ("", "en", "en"), ("hi", "en", "en"),
                                                          ("", "hinglish", "hi"), ("", None, None)])
def test_language_choice_reaches_whisper(whisper, monkeypatch, setting, choice, sent):
    monkeypatch.setattr(settings, "whisper_language", setting)
    assert transcribe.transcribe("a.wav", choice).text == "My cousin Meera and I buried a brass key in Pune."
    assert whisper.calls[-1]["language"] == sent


def test_whisper_listens_with_beam_search_vad_and_word_probabilities(whisper):
    transcribe.transcribe("a.wav")
    call = whisper.calls[-1]
    assert call["beam_size"] == 5 and call["vad_filter"] and call["word_timestamps"]


def test_known_names_and_family_words_guide_whisper(whisper):
    transcribe.transcribe("a.wav", "auto", ["Meera (cousin)", "Pune"])
    prompt = whisper.calls[-1]["initial_prompt"]
    assert prompt.startswith("Glossary: Meera, Pune,")  # names already in the archive come first
    assert "Nani" in prompt and "almirah" in prompt and "kadhi" in prompt
    assert len(prompt) <= transcribe.MAX_PROMPT_CHARS


def test_hinglish_shows_whisper_english_words_in_latin_script(whisper):
    transcribe.transcribe("a.wav", "hinglish")
    assert "school" in whisper.calls[-1]["initial_prompt"] and "मैं" in whisper.calls[-1]["initial_prompt"]


def test_unknown_language_code_is_explained(whisper, monkeypatch):
    monkeypatch.setattr(settings, "whisper_language", "xx")
    with pytest.raises(transcribe.TranscribeError, match="GW_WHISPER_LANGUAGE"):
        transcribe.transcribe("a.wav")


def test_clear_speech_passes_the_quality_check(whisper):
    quality = transcribe.transcribe("a.wav").quality
    assert not quality.unclear
    assert quality.scripts == ["LATIN"] and quality.low_ratio == 0


def test_a_noisy_recording_heard_as_the_wrong_language_is_unclear(monkeypatch):
    # The real story 6: Urdu detected with p=0.56, logprob -0.67, 29% unsure words, no-speech 0.50.
    words = "برو کل اوکن تک اپرچز کا عورجنل برشن آ رہا ہے ہندی والا اوکن تک اپرچز اوکن تک اپرچز اس کے"
    fake = FakeWhisper([segment(words, logprob=-0.67, no_speech=0.5, ratio=1.9, unsure=6)], language_probability=0.56)
    monkeypatch.setattr(transcribe, "_model", lambda: fake)
    quality = transcribe.transcribe("a.wav").quality
    assert quality.unclear and quality.low_words[:2] == ["برو", "کل"]


def test_words_in_several_alphabets_are_unclear(monkeypatch):
    fake = FakeWhisper([segment("ते 그리고 and نہیں the memory of a lamp on the terrace")])
    monkeypatch.setattr(transcribe, "_model", lambda: fake)
    quality = transcribe.transcribe("a.wav").quality
    assert quality.scripts == ["ARABIC", "DEVANAGARI", "HANGUL", "LATIN"]
    assert "several alphabets" in quality.reasons[0]


def test_hindi_with_english_words_is_not_unclear(monkeypatch):
    fake = FakeWhisper([segment("मैं school से आता था, तो Dadi हमेशा chai बनाती थीं।")])
    monkeypatch.setattr(transcribe, "_model", lambda: fake)
    assert not transcribe.transcribe("a.wav", "hinglish").quality.unclear


def test_a_repetition_loop_or_a_wrong_forced_language_is_unclear(monkeypatch):
    loop = FakeWhisper([segment("the lamp the lamp the lamp the lamp", ratio=3.1)])
    monkeypatch.setattr(transcribe, "_model", lambda: loop)
    assert transcribe.transcribe("a.wav").quality.unclear
    # English speech forced to Hindi: measured logprob -1.70.
    forced = FakeWhisper([segment("मैं कस मैर of मैर अद बारेड", logprob=-1.7, unsure=5)])
    monkeypatch.setattr(transcribe, "_model", lambda: forced)
    assert transcribe.transcribe("a.wav", "hi").quality.unclear
