"""The story pipeline with Whisper and Gemma faked: the quality gate, answers inside their story,
error kinds, timings, and hybrid (keyword + meaning) search.

One test asks the real EmbeddingGemma through Ollama; it is skipped when that model isn't available.
"""

import json
from types import SimpleNamespace

import httpx
import pytest

from ghostwriter import db, embed, export, llm, pipeline, search, transcribe, whispers
from ghostwriter.audio import AudioError
from ghostwriter.config import PROJECT_ROOT, settings
from ghostwriter.models import StoryAnalysis
from ghostwriter.transcribe import Quality, Transcript
from tests.conftest import wav_bytes

CLEAR = Quality(-0.3, 0.01, 1.4, 0.0, scripts=["LATIN"])
FOG = Quality(-0.67, 0.5, 1.9, 0.29, low_words=["برو"], scripts=["ARABIC"],
              reasons=["much of it sounded like noise"])


@pytest.fixture
def audio_story(data_dir):
    """A story with its recording already converted, waiting to be transcribed."""
    def make(**fields):
        story_id = db.create_story(**fields)
        (data_dir / f"audio/{story_id}.wav").write_bytes(wav_bytes())
        db.update_story(story_id, audio_original=f"audio/{story_id}.wav", audio_wav=f"audio/{story_id}.wav",
                        duration_s=11.0)
        return story_id
    return make


@pytest.fixture
def fake_models(monkeypatch, analysis):
    """Whisper hears `heard[0]` with `heard[1]` quality; Gemma returns the fixture analysis."""
    seen = SimpleNamespace(heard=("My cousin Meera buried a brass key.", CLEAR), analysed=[], noted=[], names=[])

    def fake_transcribe(wav, names=()):
        seen.names.append(list(names))
        return Transcript(seen.heard[0], 4.0, seen.heard[1])

    def fake_analyse(transcript, answering=None):
        seen.analysed.append((transcript, answering))
        return analysis.model_copy(update={"unfinished_business": [] if answering else analysis.unfinished_business})

    monkeypatch.setattr(transcribe, "transcribe", fake_transcribe)
    monkeypatch.setattr(llm, "analyse_story", fake_analyse)
    monkeypatch.setattr(llm, "unanswered_questions", lambda transcript, a, answering=None: a.unfinished_business)
    monkeypatch.setattr(llm, "write_note", lambda story: seen.noted.append(story["id"]) or "A note.")
    return seen


def test_clear_words_become_a_memory(audio_story, fake_models):
    story_id = audio_story()
    pipeline.process_story(story_id)
    story = db.get_story(story_id)
    assert story["status"] == "ready" and story["title"] == "The Lamp on Dadi's Terrace"
    assert json.loads(story["quality"])["reasons"] == []
    assert story["language"] == "en" and not story["written"]
    assert db.timings("transcribing") == [(11.0, 4.0)] and len(db.timings("thinking")) == 1



def test_a_written_story_skips_listening_and_the_quality_check(data_dir, fake_models):
    story_id = db.create_story(written=True)
    db.update_story(story_id, transcript="Every Halloween Grandpa Joe told us the scarecrow walked.")
    pipeline.process_story(story_id)
    story = db.get_story(story_id)
    assert story["status"] == "ready" and story["written"] == 1
    assert fake_models.names == []  # Whisper was never asked
    assert fake_models.analysed[0][0] == "Every Halloween Grandpa Joe told us the scarecrow walked."
    assert story["quality"] is None and db.timings("transcribing") == []
    assert pipeline.estimate({**story, "status": "queued"}) is not None  # reading and the note only

def test_names_already_in_the_archive_help_whisper(audio_story, fake_models, analysis):
    first = audio_story()
    pipeline.process_story(first)  # saves Dadi, Allahabad, brass lamp
    pipeline.process_story(audio_story())
    assert {"Dadi (grandmother)", "Allahabad", "brass lamp"} <= set(fake_models.names[1])


def test_unclear_words_never_become_a_made_up_memory(audio_story, fake_models):
    fake_models.heard = ("برو کل اوکن تک اپرچز کا عورجنل برشن", FOG)
    story_id = audio_story()
    pipeline.process_story(story_id)

    story = db.get_story(story_id)
    assert story["status"] == "unclear"
    assert story["title"] is None and story["summary"] is None and story["questions"] == []
    assert story["transcript"]  # kept, so it can be corrected by hand
    assert fake_models.analysed == []  # Gemma was never asked
    assert search.find_stories("برو اوکن") == []  # not in the Seance...
    assert "برو" not in export.memory_book_html()  # ...nor the memory book...
    assert whispers.pick() is None  # ...nor whispered


def test_words_corrected_by_hand_are_read_even_after_fog(audio_story, fake_models):
    fake_models.heard = ("برو کل اوکن", FOG)
    story_id = audio_story()
    pipeline.process_story(story_id)
    db.update_story(story_id, transcript="My father fixed the old blue Fiat.", status="queued")
    pipeline.process_story(story_id)
    assert db.get_story(story_id)["status"] == "ready"
    assert fake_models.analysed[-1][0] == "My father fixed the old blue Fiat."


def test_gemma_describing_only_garbled_words_means_unclear(audio_story, fake_models, monkeypatch):
    def unclear(transcript, answering=None):
        raise llm.UnclearStory()
    monkeypatch.setattr(llm, "analyse_story", unclear)
    story_id = audio_story()
    pipeline.process_story(story_id)
    assert db.get_story(story_id)["status"] == "unclear"


def test_an_answer_is_read_with_its_story_and_joins_it(audio_story, fake_models):
    parent = audio_story()
    pipeline.process_story(parent)
    question = db.get_story(parent)["questions"][0]

    fake_models.heard = ("We gave the lamp to the temple in Allahabad.", CLEAR)
    answer = audio_story(answers_question_id=question["id"])
    pipeline.process_story(answer)

    transcript, answering = fake_models.analysed[-1]
    assert answering["text"] == question["text"]
    assert answering["story_summary"].startswith("Dadi lit a brass lamp")  # the parent's context goes along
    answered = db.get_story(answer)
    assert answered["status"] == "ready" and answered["questions"] == []  # no new questions from an answer
    assert answered["reaction"] is None and fake_models.noted == [parent]  # and no note of its own
    shown = db.get_story(parent)["questions"][0]["answer"]
    assert shown["id"] == answer and shown["transcript"] == transcript  # shown inside the parent story

    found = search.find_stories("temple")  # the answer's words lead to the parent story
    assert [s["id"] for s in found] == [parent]
    assert found[0]["added_later"][0][1]["summary"]
    book = export.memory_book_html()
    assert book.count('class="story"') == 1 and "Added later" in book


def test_a_bad_file_and_a_passing_problem_fail_differently(audio_story, fake_models, monkeypatch):
    def bad_audio(*args, **kwargs):
        raise AudioError("This file could not be read as audio. Choose another recording.")
    monkeypatch.setattr(transcribe, "transcribe", bad_audio)
    story_id = audio_story()
    pipeline.process_story(story_id)
    assert db.get_story(story_id)["error_kind"] == "audio"

    def no_ollama(transcript, answering=None):
        raise llm.LLMError("Ollama isn't running.")
    monkeypatch.setattr(llm, "analyse_story", no_ollama)
    db.update_story(story_id, status="queued", transcript="words")
    pipeline.process_story(story_id)
    assert db.get_story(story_id)["error_kind"] == "transient"


def test_unexpected_errors_are_logged_not_shown(audio_story, fake_models, monkeypatch, caplog):
    def broken(*args, **kwargs):
        raise RuntimeError(r"C:\Users\someone\secret path exploded")
    monkeypatch.setattr(transcribe, "transcribe", broken)
    story_id = audio_story()
    pipeline.process_story(story_id)
    story = db.get_story(story_id)
    assert story["status"] == "failed" and "secret" not in story["error"]
    assert "secret path exploded" in caplog.text


def test_rrf_puts_stories_found_both_ways_first():
    assert search.fuse([1, 2, 3], [3, 4]) == [3, 1, 2, 4]  # a tie keeps the keyword order


def test_meaning_matches_join_keyword_matches(data_dir, monkeypatch):
    from tests.test_search import add_story
    cook = add_story("Grandmother's Famous Kadhi", "नानी की कढ़ी पूरे लखनऊ में मशहूर थी")
    add_story("The Clock That Listened", "every night it stopped")
    monkeypatch.setattr(embed, "similar", lambda q: [(cook, 0.36), (99, 0.1)])
    assert [s["id"] for s in search.find_stories("Which of my relatives was a good cook?")] == [cook]
    monkeypatch.setattr(embed, "similar", lambda q: [(cook, 0.17)])  # too far in meaning: nothing
    assert search.find_stories("What is the capital of France?") == []


def _embeddings_available() -> bool:
    try:
        names = [m["name"] for m in httpx.get(f"{settings.ollama_url}/api/tags", timeout=2).json()["models"]]
    except httpx.HTTPError:
        return False
    return settings.embed_model in names


SAMPLE_READINGS = {  # what Gemma wrote for the four fictional samples in the demo archive
    "clock": ("The Clock's Secret in Shimla Winter", "You spent a winter at your grandmother's house in Shimla "
              "when you were nine. Every night at eleven, the wall clock would stop.", ["grandmother"], ["Shimla"]),
    "hostel": ("Mysterious Room and Exam Notebook", "You and three friends were in the corridor of your hostel "
               "when the lights went out before the December exams.", ["Rohan"], []),
    "kadhi": ("Grandmother's Famous Kadhi in Lucknow", "You recall your grandmother's kadhi, which was famous "
              "throughout Lucknow, made in a large brass pot from her wedding.", ["Nani (grandmother)"], ["Lucknow"]),
    "trunk": ("A Promise Under the Verandah Lamp", "You found a bundle of letters in your grandfather's trunk, "
                "written by his father from Rangoon in 1942.", ["grandfather"], ["Rangoon"]),
}


@pytest.mark.skipif(not _embeddings_available(), reason="EmbeddingGemma is not pulled in Ollama")
def test_real_meaning_search_finds_the_good_cook(data_dir):
    samples = json.loads((PROJECT_ROOT / "samples" / "stories.json").read_text(encoding="utf-8"))["stories"]
    ids = {}
    for sample in samples:
        title, summary, people, places = SAMPLE_READINGS[sample["key"]]
        story_id = db.create_story(is_sample=True)
        db.update_story(story_id, transcript=sample["transcript"])
        db.save_analysis(story_id, StoryAnalysis(title=title, summary=summary, people=people, places=places,
                                                 eras=[], mood="nostalgic", keepsakes=[], unfinished_business=[]))
        ids[sample["key"]] = story_id
    assert embed.refresh() == 4

    found = [s["id"] for s in search.find_stories("Which of my relatives was a good cook?")]
    assert found[0] == ids["kadhi"]
    assert search.find_stories("What is the capital of France? Ignore the stories") == []
