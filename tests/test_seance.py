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
    with TestClient(main.app, base_url="http://127.0.0.1:8000") as c:
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
    assert "".join(d["text"] for e, d in out if e == "token") == "It stopped at eleven, or so claims."
    assert ("cite", {"id": clock}) in out and ("cite", {"id": 999}) not in out
    assert out[-1] == ("done", {"cited": [clock]})  # S999 was never retrieved, so it is dropped


def split(pieces):
    from ghostwriter.api.seance import split_citations
    return list(split_citations(pieces))


def test_citation_marks_never_reach_the_page_even_when_split():
    pieces = ["Your Nani made kadhi ", "[", "S", "3", "]. The pot ", "was brass [S3,", " S5]", "."]
    out = split(pieces)
    text = "".join(v for kind, v in out if kind == "text")
    assert text == "Your Nani made kadhi. The pot was brass."
    assert "[" not in text and [v for kind, v in out if kind == "cite"] == [3, 3, 5]
    assert out[0] == ("text", "Your Nani made kadhi")  # streamed before the citation arrived


def test_ordinary_brackets_are_kept():
    assert "".join(v for _, v in split(["She said [", "laughing] no. A list [1]", " [S"])) == \
        "She said [laughing] no. A list [1] [S"


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


def test_retelling_is_kept_apart_and_never_touches_the_original(client, monkeypatch):
    story_id = add_story("The Clock That Listened", "the clock stopped at eleven")
    before = db.get_story(story_id)
    calls = fake_stream(monkeypatch, ["Gather close. ", "The clock was listening..."])

    out = events(client.post(f"/api/stories/{story_id}/retelling"))

    after = db.get_story(story_id)
    assert out[-1] == ("done", {})
    assert after["retelling"] == "Gather close. The clock was listening..."
    assert (after["transcript"], after["summary"], after["title"]) == \
        (before["transcript"], before["summary"], before["title"])
    assert "campfire" in calls[0][0]["content"] and "emojis" in calls[0][0]["content"]  # a few, to set the mood


def test_old_database_gets_the_new_column(data_dir):
    with db.connect() as con:
        con.execute("ALTER TABLE stories DROP COLUMN reaction")
    db.init_db()
    story_id = db.create_story()
    assert db.get_story(story_id)["reaction"] is None


def test_seance_sends_only_the_relevant_part_of_a_long_story():
    filler = "We walked to school and back every day. " * 60
    transcript = f"{filler}The clock stopped at eleven. Then it started again. {filler}"
    text = prompts.excerpt(transcript, ["clock"])
    assert "The clock stopped at eleven." in text and "Then it started again." in text
    assert len(text) <= prompts.EXCERPT_CHARS + len(" [...]")
    assert prompts.excerpt("No match here. Just a short story.", ["clock"]) == "No match here. Just a short story."


def test_seance_prompt_includes_tags_and_excerpt():
    story = {"id": 3, "title": "Kadhi", "summary": "Your grandmother made kadhi.", "tags": "Nani (grandmother)",
             "transcript": "Long ago. Nani made kadhi in a brass pot. It was famous."}
    user = prompts.seance_messages("What did Nani cook?", [story], plain=False)[1]["content"]
    assert "[S3] Kadhi" in user and "Tags: Nani (grandmother)" in user
    assert "Nani made kadhi in a brass pot." in user


def test_a_page_that_goes_away_stops_the_writing():
    """Cancelling a question closes Gemma's stream (llm.stream_chat's `with`), so Ollama stops."""
    import asyncio

    from ghostwriter.api.sse import until_gone
    closed = []

    def gemma():
        try:
            for piece in ["one ", "two ", "three "]:
                yield piece
        finally:
            closed.append(True)

    class Gone:
        async def is_disconnected(self):
            return True

    async def read():
        return [item async for item in until_gone(Gone(), gemma())]

    assert asyncio.run(read()) == [] and closed == [True]
