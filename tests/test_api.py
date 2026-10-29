"""API tests. The pipeline is replaced by a fake, so no ffmpeg, Whisper or Gemma is needed."""

import pytest
from fastapi.testclient import TestClient

from ghostwriter import db, pipeline
from ghostwriter.api import main


@pytest.fixture
def client(data_dir, analysis, monkeypatch):
    def fake_process(story_id):
        db.update_story(story_id, transcript="a fake transcript", language="en")
        db.save_analysis(story_id, analysis)

    monkeypatch.setattr(pipeline, "process_story", fake_process)
    monkeypatch.setattr(main.selfcheck, "run_checks", lambda: [])
    with TestClient(main.app) as c:
        yield c


def upload(client, name="memory.m4a", data=b"fake audio bytes", **form):
    return client.post("/api/stories", files={"file": (name, data)}, data=form)


def test_upload_creates_a_tagged_story(client, data_dir):
    resp = upload(client)
    assert resp.status_code == 201
    story_id = resp.json()["id"]

    story = client.get(f"/api/stories/{story_id}").json()
    assert story["status"] == "ready"
    assert story["title"] == "The Lamp on Dadi's Terrace"
    assert (data_dir / story["audio_original"]).read_bytes() == b"fake audio bytes"
    assert [s["id"] for s in client.get("/api/stories").json()] == [story_id]


def test_original_audio_is_served_back(client):
    story_id = upload(client).json()["id"]
    resp = client.get(f"/api/stories/{story_id}/audio")
    assert resp.status_code == 200
    assert resp.content == b"fake audio bytes"


def test_unsupported_and_empty_files_are_rejected(client):
    assert upload(client, name="virus.exe").status_code == 415
    assert upload(client, data=b"").status_code == 400
    assert client.get("/api/stories").json() == []  # nothing half-saved


def test_answering_unfinished_business(client):
    first = upload(client).json()["id"]
    question_id = client.get(f"/api/stories/{first}").json()["questions"][0]["id"]

    answer = upload(client, answers_question_id=str(question_id)).json()["id"]

    assert client.get(f"/api/stories/{first}").json()["questions"][0]["answered_by"] == answer
    assert upload(client, answers_question_id="9999").status_code == 404


def test_missing_story_answers_in_character(client):
    resp = client.get("/api/stories/42")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "That memory was never given to me."


def test_visiting_relights_the_candle(client):
    story_id = upload(client).json()["id"]
    db.update_story(story_id, last_visited_at="2020-01-01 00:00:00")
    assert client.post(f"/api/stories/{story_id}/visit").status_code == 204
    assert client.get(f"/api/stories/{story_id}").json()["last_visited_at"] > "2026"
    assert client.post("/api/stories/999/visit").status_code == 404


def test_only_failed_stories_can_be_retried(client):
    story_id = upload(client).json()["id"]
    assert client.post(f"/api/stories/{story_id}/retry").status_code == 409


def test_opening_the_page_warms_up_gemma(client, monkeypatch):
    calls = []
    monkeypatch.setattr(main.llm, "warm_up", lambda: calls.append(1))
    assert client.post("/api/warm").status_code == 204
    assert calls == [1]


def test_editing_keeps_whispers_original_words(client):
    story_id = upload(client).json()["id"]
    resp = client.patch(f"/api/stories/{story_id}", json={"title": "The Blue Fiat", "transcript": "an old blue Fiat"})
    assert resp.status_code == 200
    story = resp.json()
    assert story["title"] == "The Blue Fiat" and story["transcript"] == "an old blue Fiat"
    assert story["transcript_original"] == "a fake transcript"

    client.patch(f"/api/stories/{story_id}", json={"transcript": "an old blue Fiat, again"})
    assert client.get(f"/api/stories/{story_id}").json()["transcript_original"] == "a fake transcript"
    assert client.patch(f"/api/stories/{story_id}", json={"title": ""}).status_code == 422
    assert client.patch("/api/stories/999", json={"title": "x"}).status_code == 404


def test_edited_title_is_searchable(client):
    from ghostwriter import search
    story_id = upload(client).json()["id"]
    client.patch(f"/api/stories/{story_id}", json={"title": "The Blue Fiat"})
    assert [s["id"] for s in search.find_stories("fiat")] == [story_id]


def test_reread_queues_a_fresh_analysis(client, monkeypatch):
    story_id = upload(client).json()["id"]
    db.update_story(story_id, reaction="an old note", retelling="an old retelling")
    queued = []
    monkeypatch.setattr(pipeline, "process_story", lambda i: queued.append((i, db.get_story(i)["status"])))

    assert client.post(f"/api/stories/{story_id}/reread").status_code == 202
    assert queued == [(story_id, "queued")]
    story = client.get(f"/api/stories/{story_id}").json()
    assert story["reaction"] is None  # the note is rewritten for the new words...
    assert story["retelling"] == "an old retelling"  # ...the retelling and the recording are kept
    assert story["audio_original"]


def test_stories_being_processed_cannot_be_changed(client):
    story_id = upload(client).json()["id"]
    db.update_story(story_id, status="thinking")
    assert client.patch(f"/api/stories/{story_id}", json={"title": "x"}).status_code == 409
    assert client.post(f"/api/stories/{story_id}/reread").status_code == 409
    assert client.delete(f"/api/stories/{story_id}").status_code == 409


def test_delete_removes_everything_of_the_story(client, data_dir):
    first = upload(client).json()["id"]
    question_id = client.get(f"/api/stories/{first}").json()["questions"][0]["id"]
    answer = upload(client, answers_question_id=str(question_id)).json()["id"]
    story = client.get(f"/api/stories/{first}").json()
    db.update_story(first, reaction="A note.", audio_wav=f"audio/{first}.wav")
    (data_dir / f"audio/{first}.wav").write_bytes(b"wav")
    from ghostwriter import tts
    voice = tts.cache_path("A note.", True)
    voice.parent.mkdir(parents=True, exist_ok=True)
    voice.write_bytes(b"spoken")

    assert client.delete(f"/api/stories/{first}").status_code == 204

    assert client.get(f"/api/stories/{first}").status_code == 404
    assert not (data_dir / story["audio_original"]).exists() and not (data_dir / f"audio/{first}.wav").exists()
    assert not voice.exists()
    with db.connect() as con:
        assert con.execute("SELECT count(*) FROM entities WHERE story_id = ?", (first,)).fetchone()[0] == 0
        assert con.execute("SELECT count(*) FROM questions WHERE story_id = ?", (first,)).fetchone()[0] == 0
        assert con.execute("SELECT count(*) FROM stories_fts WHERE stories_fts MATCH 'Terrace'").fetchone()[0] == 1
    survivor = client.get(f"/api/stories/{answer}").json()  # the answer stays, as a story of its own
    assert survivor["answers_question_id"] is None
    assert client.delete("/api/stories/999").status_code == 404


def test_tags_can_be_renamed_merged_and_removed(client):
    story_id = upload(client).json()["id"]  # the fixture analysis has person "Dadi (grandmother)"
    rename = lambda **edit: client.post(f"/api/stories/{story_id}/tags", json=edit)  # noqa: E731

    assert rename(kind="person", old="Dadi (grandmother)", new="Dadi").json()["entities"]["person"] == ["Dadi"]
    client.post(f"/api/stories/{story_id}/tags", json={"kind": "person", "old": "Dadi", "new": "Nani"})
    db.rename_tag(story_id, "place", "Allahabad", "Prayagraj")
    story = client.get(f"/api/stories/{story_id}").json()
    assert story["entities"]["place"] == ["Prayagraj"] and "Prayagraj" in story["tags"]
    with db.connect() as con:  # merging: renaming to a tag the story already has keeps one
        con.execute("INSERT INTO entities (story_id, kind, value) VALUES (?, 'person', 'Dadi')", (story_id,))
    assert rename(kind="person", old="Dadi", new="Nani").json()["entities"]["person"] == ["Nani"]
    assert "person" not in rename(kind="person", old="Nani", new="").json()["entities"]
    assert rename(kind="mood", old="x", new="y").status_code == 422
