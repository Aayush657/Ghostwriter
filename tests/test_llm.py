"""LLM layer tests with Ollama mocked: JSON validation, the one-time repair, and friendly errors."""

import json

import httpx
import pytest

from ghostwriter import llm, prompts
from ghostwriter.config import settings
from ghostwriter.models import StoryAnalysis


def fake_replies(monkeypatch, replies):
    """Make llm.chat return the given replies in order, and record every call."""
    calls = []

    def fake_chat(messages, **kwargs):
        calls.append((list(messages), kwargs))
        return replies[len(calls) - 1]

    monkeypatch.setattr(llm, "chat", fake_chat)
    return calls


def test_valid_json_is_accepted_first_time(monkeypatch, analysis):
    calls = fake_replies(monkeypatch, [analysis.model_dump_json()])
    assert llm.analyse_story("a story") == analysis
    assert len(calls) == 1
    assert calls[0][1]["temperature"] == 0  # re-reading the same words gives the same result


def test_bad_json_gets_one_repair(monkeypatch, analysis):
    no_title = {k: v for k, v in analysis.model_dump().items() if k != "title"}
    calls = fake_replies(monkeypatch, [json.dumps(no_title), analysis.model_dump_json()])

    assert llm.analyse_story("a story") == analysis
    assert len(calls) == 2
    assert "did not match" in calls[1][0][-1]["content"]  # the repair request explains the problem


def test_two_bad_replies_raise_a_friendly_error(monkeypatch):
    fake_replies(monkeypatch, ["not json", "{still not json"])
    with pytest.raises(llm.LLMError, match="couldn't make sense"):
        llm.analyse_story("a story")


def test_talk_about_the_transcript_is_repaired(monkeypatch, analysis):
    meta = analysis.model_copy(update={"summary": "The transcript provided contains a story about a lamp."})
    calls = fake_replies(monkeypatch, [meta.model_dump_json(), analysis.model_dump_json()])
    assert llm.analyse_story("a story").summary == analysis.summary
    assert "transcript" in calls[1][0][-1]["content"]  # Gemma is told what was wrong


def test_a_reply_that_only_describes_garbled_words_means_unclear(monkeypatch, analysis):
    meta = analysis.model_copy(update={"summary": "The transcription is fragmented and unintelligible."})
    fake_replies(monkeypatch, [meta.model_dump_json(), meta.model_dump_json()])
    with pytest.raises(llm.UnclearStory):
        llm.analyse_story("برو کل اوکن تک")


@pytest.mark.parametrize("phrase", ["As an AI, I think", "The speaker remembers", "Based on the provided text"])
def test_meta_text_never_validates(analysis, phrase):
    with pytest.raises(ValueError):
        StoryAnalysis(**{**analysis.model_dump(), "summary": f"{phrase} a lamp."})


def test_out_of_memory_says_what_to_do(monkeypatch):
    error = '{"error":"llama-server startup failed: unable to allocate CPU_REPACK buffer"}'
    monkeypatch.setattr(llm.httpx, "post", lambda *args, **kwargs: httpx.Response(500, text=error))
    with pytest.raises(llm.LLMError, match="Close some programs"):
        llm.chat([{"role": "user", "content": "hello"}])


def test_ollama_down_gives_a_plain_fix(monkeypatch):
    monkeypatch.setattr(settings, "ollama_url", "http://127.0.0.1:9")
    with pytest.raises(llm.LLMError, match="ollama serve"):
        llm.chat([{"role": "user", "content": "hello"}])


def test_gemma_must_pick_one_of_the_candle_moods():
    schema = StoryAnalysis.model_json_schema()
    assert schema["properties"]["mood"]["enum"] == ["joyful", "nostalgic", "loving", "poignant", "mysterious", "eerie"]


@pytest.mark.parametrize(("given", "kept"), [("Eerie", "eerie"), ("confused", "mysterious"), ("sad", "poignant"),
                                              ("calm", "nostalgic"), ("bewildered", "nostalgic")])
def test_moods_outside_the_list_fall_back_to_a_candle_mood(analysis, given, kept):
    assert StoryAnalysis(**{**analysis.model_dump(), "mood": given}).mood == kept


def test_old_moods_in_the_database_are_fixed(data_dir):
    from ghostwriter import db
    story_id = db.create_story()
    db.update_story(story_id, mood="confused")
    db.init_db()
    assert db.get_story(story_id)["mood"] == "mysterious"


def test_analysis_tags_are_tidied(monkeypatch, analysis):
    messy = analysis.model_copy(update={"places": ["Allahabad", "the corridor"], "eras": ["1990s", "the past"]})
    fake_replies(monkeypatch, [messy.model_dump_json()])
    result = llm.analyse_story("a story")
    assert result.places == ["Allahabad"] and result.eras == ["1990s"]


def test_an_answer_is_read_with_its_story_and_asks_nothing_new(monkeypatch, analysis):
    answering = {"id": 1, "story_id": 1, "text": "What happened to the brass lamp?",
                 "story_title": "The Lamp on Dadi's Terrace", "story_summary": "Dadi lit a brass lamp every Diwali."}
    calls = fake_replies(monkeypatch, [analysis.model_dump_json()])
    result = llm.analyse_story("We gave it to the temple.", answering)
    assert result.unfinished_business == []
    system, user = calls[0][0][0]["content"], calls[0][0][1]["content"]
    assert "Dadi lit a brass lamp every Diwali." in user and "What happened to the brass lamp?" in user
    assert "an empty list" in system
    assert llm.unanswered_questions("We gave it to the temple.", result, answering) == []  # nothing to check


def check(about, answered=False, unknown=False):
    return {"about": about, "answered": answered, "unknown": unknown}


def test_questions_the_story_answers_or_cannot_are_dropped(monkeypatch, analysis):
    story = "Dadi lit a brass lamp on the terrace. Who lit it the next year, nobody knows."
    reply = json.dumps({"checks": [check("a brass lamp"), check("Who lit it the next year", unknown=True)]})
    calls = fake_replies(monkeypatch, [reply])
    two = analysis.model_copy(update={"unfinished_business": ["What did the lamp look like?", "Who lit it the next year?"]})
    assert llm.unanswered_questions(story, two) == ["What did the lamp look like?"]
    assert calls[0][0][-2]["role"] == "assistant"  # same conversation, so Ollama reuses what it read
    assert "never found out" in calls[0][0][-1]["content"]

    fake_replies(monkeypatch, [json.dumps({"checks": [check("brass lamp on the terrace", answered=True), check("")]})])
    assert llm.unanswered_questions(story, two) == ["Who lit it the next year?"]


def test_nobody_knows_counts_only_when_the_story_says_so(monkeypatch, analysis):
    story = ("My cousin Meera and I buried a brass key under the mango tree in Pune in 2009. Meera always believed "
             "the key opened the locked almirah in our grandfather's room. We never found the lock it opened.")
    questions = ["What did the almirah look like?", "What happened after you buried the key?", "Where is the lock?"]
    reply = json.dumps({"checks": [check("the locked almirah in our grandfather's room", unknown=True),
                                   check("buried a brass key under the mango tree", unknown=True),
                                   check("We never found the lock it opened", unknown=True)]})
    fake_replies(monkeypatch, [reply])
    kept = llm.unanswered_questions(story, analysis.model_copy(update={"unfinished_business": questions}))
    assert kept == questions[:2]  # Gemma called them unknown too, but their sentences don't say so


@pytest.mark.parametrize("sentence", ["My grandmother never told me who made it.", "ये मुझे नहीं पता.",
                                      "Kisne banaya, pata nahi.", "Nobody knows where it went."])
def test_ways_of_saying_nobody_knows(sentence):
    assert llm.says_unknown(f"We drank tea. {sentence}", sentence.split()[-2])


def test_question_rules_prefer_senses_and_people():
    rules = prompts.analyse_system()
    assert "smelled" in rules and "who else was there" in rules and "never found out" in rules


def test_a_failed_question_check_keeps_every_question(monkeypatch, analysis):
    fake_replies(monkeypatch, [json.dumps({"checks": [check("", answered=True)]})])  # wrong length
    assert llm.unanswered_questions("a story", analysis) == analysis.unfinished_business
    fake_replies(monkeypatch, ["not json"])
    assert llm.unanswered_questions("a story", analysis) == analysis.unfinished_business
