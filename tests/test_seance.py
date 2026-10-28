"""Seance and reaction streaming tests, with Gemma mocked."""

import json

import pytest
from fastapi.testclient import TestClient

from ghostwriter import db, llm, prompts
from ghostwriter.api import main
from tests.test_search import add_story


def events(resp) -> list[tuple[str, dict]]:
    """Parse a Server-Sent Events body into (event, data) pairs."""
    out = []
    for block in resp.text.strip().split("\n\n"):
        name, data = block.split("\n", 1)
        out.append((name.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
    return out


@pytest.fixture
def client(data_dir, monkeypatch):
    monkeypatch.setattr(main.selfcheck, "run_checks", lambda: [])
    with TestClient(main.app) as c:
        yield c


def fake_stream(monkeypatch, pieces):
    calls = []

    def fake(messages, **kwargs):
        calls.append(messages)
        yield from pieces

    monkeypatch.setattr(llm, "stream_chat", fake)
    return calls


def test_no_matching_story_means_gemma_is_never_asked(client, monkeypatch):
    calls = fake_stream(monkeypatch, ["invented!"])
    out = events(client.post("/api/seance", json={"question": "Who built the lighthouse?"}))
    assert out[0] == ("sources", {"stories": []})
    assert out[1] == ("token", {"text": prompts.UNKNOWN[False]})
    assert calls == []


def test_answer_streams_and_only_real_citations_count(client, monkeypatch):
    clock = add_story("The Clock That Listened", "the clock stopped at eleven")
    fake_stream(monkeypatch, ["It stopped at eleven ", f"[S{clock}]", ", or so [S999] claims."])

    out = events(client.post("/api/seance", json={"question": "When did the clock stop?"}))

    assert out[0] == ("sources", {"stories": [{"id": clock, "title": "The Clock That Listened"}]})
    assert "".join(d["text"] for e, d in out if e == "token").startswith("It stopped at eleven")
    assert out[-1] == ("done", {"cited": [clock]})  # S999 was never retrieved, so it is dropped


def test_plain_mode_changes_the_voice(client, monkeypatch):
    add_story("The Clock That Listened", "tick")
    calls = fake_stream(monkeypatch, ["ok"])
    client.post("/api/seance", json={"question": "clock?", "plain": True})
    assert calls[0][0]["content"].startswith(prompts.PLAIN)


def test_gemma_down_becomes_an_error_event(client, monkeypatch):
    add_story("The Clock That Listened", "tick")

    def broken(messages, **kwargs):
        raise llm.LLMError("Ollama isn't running.")
        yield  # pragma: no cover

    monkeypatch.setattr(llm, "stream_chat", broken)
    out = events(client.post("/api/seance", json={"question": "clock?"}))
    assert out[-1] == ("error", {"message": "Ollama isn't running."})


def test_reaction_is_written_once_then_remembered(client, monkeypatch):
    story_id = add_story("The Clock That Listened", "tick")
    calls = fake_stream(monkeypatch, ["How the clock ", "listens..."])

    first = events(client.post(f"/api/stories/{story_id}/reaction"))
    second = events(client.post(f"/api/stories/{story_id}/reaction"))

    assert [d["text"] for e, d in first if e == "token"] == ["How the clock ", "listens..."]
    assert second[0] == ("token", {"text": "How the clock listens..."})
    assert len(calls) == 1
    assert db.get_story(story_id)["reaction"] == "How the clock listens..."


def test_old_database_gets_the_new_column(data_dir):
    with db.connect() as con:
        con.execute("ALTER TABLE stories DROP COLUMN reaction")
    db.init_db()
    story_id = db.create_story()
    assert db.get_story(story_id)["reaction"] is None
