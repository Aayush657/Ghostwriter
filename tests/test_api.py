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
