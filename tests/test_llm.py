"""LLM layer tests with Ollama mocked: JSON validation, the one-time repair, and friendly errors."""

import json

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


def test_ollama_down_gives_a_plain_fix(monkeypatch):
    monkeypatch.setattr(settings, "ollama_url", "http://127.0.0.1:9")
    with pytest.raises(llm.LLMError, match="ollama serve"):
        llm.chat([{"role": "user", "content": "hello"}])
