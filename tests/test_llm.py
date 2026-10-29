"""LLM layer tests with Ollama mocked: JSON validation, the one-time repair, and friendly errors."""

import json

import httpx
import pytest

from ghostwriter import llm
from ghostwriter.config import settings


def fake_replies(monkeypatch, replies):
    """Make llm.chat return the given replies in order, and record every call."""
    calls = []

    def fake_chat(messages, **kwargs):
        calls.append(list(messages))
        return replies[len(calls) - 1]

    monkeypatch.setattr(llm, "chat", fake_chat)
    return calls


def test_valid_json_is_accepted_first_time(monkeypatch, analysis):
    calls = fake_replies(monkeypatch, [analysis.model_dump_json()])
    assert llm.analyse_story("a story") == analysis
    assert len(calls) == 1


def test_bad_json_gets_one_repair(monkeypatch, analysis):
    too_few_questions = {**analysis.model_dump(), "unfinished_business": ["Only one?"]}
    calls = fake_replies(monkeypatch, [json.dumps(too_few_questions), analysis.model_dump_json()])

    assert llm.analyse_story("a story") == analysis
    assert len(calls) == 2
    assert "did not match" in calls[1][-1]["content"]  # the repair request explains the problem


def test_two_bad_replies_raise_a_friendly_error(monkeypatch):
    fake_replies(monkeypatch, ["not json", "{still not json"])
    with pytest.raises(llm.LLMError, match="couldn't make sense"):
        llm.analyse_story("a story")


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
    from ghostwriter.models import StoryAnalysis
    schema = StoryAnalysis.model_json_schema()
    assert schema["properties"]["mood"]["enum"] == ["joyful", "nostalgic", "loving", "poignant", "mysterious", "eerie"]


def test_analysis_tags_are_tidied(monkeypatch, analysis):
    messy = analysis.model_copy(update={"places": ["Allahabad", "the corridor"], "eras": ["1990s", "the past"]})
    fake_replies(monkeypatch, [messy.model_dump_json()])
    result = llm.analyse_story("a story")
    assert result.places == ["Allahabad"] and result.eras == ["1990s"]


def test_questions_the_transcript_answers_are_dropped(monkeypatch, analysis):
    calls = fake_replies(monkeypatch, ['{"answered": [false, true]}'])
    kept = llm.unanswered_questions("Dadi lit a brass lamp on the terrace.", analysis)
    assert kept == ["What happened to the brass lamp?"]
    assert calls[0][-2]["role"] == "assistant"  # same conversation, so Ollama reuses what it read


def test_a_failed_question_check_keeps_every_question(monkeypatch, analysis):
    fake_replies(monkeypatch, ['{"answered": [true]}'])  # wrong length
    assert llm.unanswered_questions("a story", analysis) == analysis.unfinished_business
    fake_replies(monkeypatch, ["not json"])
    assert llm.unanswered_questions("a story", analysis) == analysis.unfinished_business
