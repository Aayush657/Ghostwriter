"""API tests. The pipeline is replaced by a fake, so no Whisper or Gemma is needed.
Uploads are checked with the real ffprobe when it is installed."""

import shutil

import pytest
from fastapi.testclient import TestClient

from ghostwriter import db, pipeline, trash
from ghostwriter.api import main
from ghostwriter.config import settings
from tests.conftest import wav_bytes

has_ffprobe = shutil.which(settings.ffprobe) is not None
WAV = wav_bytes()


@pytest.fixture
def client(data_dir, analysis, monkeypatch):
    def fake_process(story_id):
        db.update_story(story_id, transcript="a fake transcript", language="en")
        db.save_analysis(story_id, analysis)

    monkeypatch.setattr(pipeline, "process_story", fake_process)
    monkeypatch.setattr(main.selfcheck, "run_checks", lambda: [])
    monkeypatch.setattr(main.embed, "refresh_quietly", lambda: None)
    with TestClient(main.app) as c:
        yield c


def upload(client, name="memory.wav", data=WAV, **form):
    return client.post("/api/stories", files={"file": (name, data)}, data=form)


def test_upload_creates_a_tagged_story(client, data_dir):
    resp = upload(client, language="hi")
    assert resp.status_code == 201
    story_id = resp.json()["id"]

    story = client.get(f"/api/stories/{story_id}").json()
    assert story["status"] == "ready"
    assert story["title"] == "The Lamp on Dadi's Terrace"
    assert story["language_choice"] == "hi"
    assert (data_dir / story["audio_original"]).read_bytes() == WAV
    assert [s["id"] for s in client.get("/api/stories").json()] == [story_id]


def test_original_audio_is_served_back(client):
    story_id = upload(client).json()["id"]
    resp = client.get(f"/api/stories/{story_id}/audio")
    assert resp.status_code == 200
    assert resp.content == WAV


def test_unsupported_and_empty_files_are_rejected(client, data_dir):
    assert upload(client, name="virus.exe").status_code == 415
    assert upload(client, data=b"").status_code == 400
    assert upload(client, language="klingon").status_code == 422
    assert client.get("/api/stories").json() == []  # nothing half-saved
    assert list((data_dir / "audio").iterdir()) == []


@pytest.mark.skipif(not has_ffprobe, reason="ffprobe is not installed")
def test_a_file_that_is_not_audio_never_becomes_a_story(client, data_dir):
    resp = upload(client, name="notes.mp3", data=b"these are my shopping notes, not a recording")
    assert resp.status_code == 415
    assert "isn't a recording" in resp.json()["detail"]
    assert "Invalid data" not in resp.json()["detail"]  # ffmpeg's own words stay in the server log
    assert client.get("/api/stories").json() == []
    assert list((data_dir / "audio").iterdir()) == []


@pytest.mark.skipif(not has_ffprobe, reason="ffprobe is not installed")
def test_too_short_and_too_long_recordings_are_refused(client, monkeypatch):
    assert "too short" in upload(client, data=wav_bytes(0.2)).json()["detail"]
    monkeypatch.setattr(settings, "max_audio_minutes", 0)
    assert "longer than 0 minutes" in upload(client).json()["detail"]
    assert client.get("/api/stories").json() == []


def test_an_answer_belongs_to_its_story(client):
    first = upload(client).json()["id"]
    question_id = client.get(f"/api/stories/{first}").json()["questions"][0]["id"]

    answer = upload(client, answers_question_id=str(question_id)).json()["id"]

    question = client.get(f"/api/stories/{first}").json()["questions"][0]
    assert question["answered_by"] == answer
    assert question["answer"]["id"] == answer and question["answer"]["transcript"] == "a fake transcript"
    listed = {s["id"]: s for s in client.get("/api/stories").json()}
    assert listed[answer]["parent_id"] == first and listed[first]["parent_id"] is None
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


def test_only_passing_failures_can_be_retried(client):
    story_id = upload(client).json()["id"]
    assert client.post(f"/api/stories/{story_id}/retry").status_code == 409  # it's ready
    db.update_story(story_id, status="failed", error="This file could not be read as audio.", error_kind="audio")
    assert client.post(f"/api/stories/{story_id}/retry").status_code == 409  # same file, same result
    db.update_story(story_id, error="Ollama isn't running.", error_kind="transient")
    assert client.post(f"/api/stories/{story_id}/retry").status_code == 202


def test_opening_the_page_wakes_the_models(client, monkeypatch):
    calls = []
    monkeypatch.setattr(main.llm, "warm_up", lambda: calls.append("gemma"))
    monkeypatch.setattr(main.transcribe, "warm_up", lambda: calls.append("whisper"))
    assert client.post("/api/warm").status_code == 204
    assert sorted(calls) == ["gemma", "whisper"]


def test_editing_keeps_whispers_original_words(client):
    story_id = upload(client).json()["id"]
    resp = client.patch(f"/api/stories/{story_id}", json={"title": "  The Blue Fiat  ", "transcript": "an old blue Fiat"})
    assert resp.status_code == 200
    story = resp.json()
    assert story["title"] == "The Blue Fiat" and story["transcript"] == "an old blue Fiat"  # trimmed
    assert story["transcript_original"] == "a fake transcript"

    client.patch(f"/api/stories/{story_id}", json={"transcript": "an old blue Fiat, again"})
    assert client.get(f"/api/stories/{story_id}").json()["transcript_original"] == "a fake transcript"
    assert client.patch("/api/stories/999", json={"title": "x"}).status_code == 404


def test_titles_are_trimmed_and_checked(client):
    story_id = upload(client).json()["id"]
    for bad in ("", "   ", "x" * 121):
        resp = client.patch(f"/api/stories/{story_id}", json={"title": bad})
        assert resp.status_code == 422
        assert resp.json()["detail"][0]["loc"][-1] == "title"  # the page turns this into plain words
    assert client.get(f"/api/stories/{story_id}").json()["title"] == "The Lamp on Dadi's Terrace"


def test_mood_can_be_changed_only_to_a_candle_mood(client):
    story_id = upload(client).json()["id"]
    assert client.patch(f"/api/stories/{story_id}", json={"mood": "joyful"}).json()["mood"] == "joyful"
    assert client.patch(f"/api/stories/{story_id}", json={"mood": "confused"}).status_code == 422


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


def test_listening_again_in_another_language(client, monkeypatch):
    story_id = upload(client).json()["id"]
    db.update_story(story_id, retelling="an old retelling")
    queued = []
    monkeypatch.setattr(pipeline, "process_story", lambda i: queued.append(db.get_story(i)))

    assert client.post(f"/api/stories/{story_id}/relisten", json={"language": "hinglish"}).status_code == 202
    story = queued[0]
    assert story["status"] == "queued" and story["language_choice"] == "hinglish"
    assert story["transcript"] is None and story["title"] is None and story["retelling"] is None
    assert story["audio_original"]  # the recording itself is kept
    assert client.post(f"/api/stories/{story_id}/relisten", json={"language": "fr"}).status_code == 422


def test_stories_being_processed_cannot_be_changed(client):
    story_id = upload(client).json()["id"]
    db.update_story(story_id, status="thinking")
    assert client.patch(f"/api/stories/{story_id}", json={"title": "x"}).status_code == 409
    assert client.post(f"/api/stories/{story_id}/reread").status_code == 409
    assert client.post(f"/api/stories/{story_id}/relisten", json={}).status_code == 409
    assert client.delete(f"/api/stories/{story_id}").status_code == 409


def test_a_story_in_progress_says_how_long_it_will_take(client):
    story_id = upload(client).json()["id"]
    db.update_story(story_id, status="queued", transcript=None, duration_s=30)
    assert client.get(f"/api/stories/{story_id}").json()["estimate_s"] is None  # nothing measured yet
    db.record_timing("transcribing", 10, audio_s=20)
    db.record_timing("thinking", 25)
    db.record_timing("noting", 8)
    assert client.get(f"/api/stories/{story_id}").json()["estimate_s"] == 15 + 25 + 8


def test_delete_can_be_undone_then_removes_everything(client, data_dir):
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
    assert client.get(f"/api/stories/{first}").status_code == 404  # gone from view at once...
    assert client.get("/api/stories").json() == []  # ...with its answer
    assert client.post(f"/api/stories/{first}/restore").status_code == 200  # Undo
    assert {s["id"] for s in client.get("/api/stories").json()} == {first, answer}

    client.delete(f"/api/stories/{first}")
    assert trash.purge(older_than=0) == 2
    assert client.post(f"/api/stories/{first}/restore").status_code == 410
    assert not (data_dir / story["audio_original"]).exists() and not (data_dir / f"audio/{first}.wav").exists()
    assert not voice.exists()
    with db.connect() as con:
        assert con.execute("SELECT count(*) FROM stories").fetchone()[0] == 0
        assert con.execute("SELECT count(*) FROM entities WHERE story_id = ?", (first,)).fetchone()[0] == 0
        assert con.execute("SELECT count(*) FROM questions WHERE story_id = ?", (first,)).fetchone()[0] == 0
        assert con.execute("SELECT count(*) FROM stories_fts WHERE stories_fts MATCH 'Terrace'").fetchone()[0] == 0
    assert list((data_dir / "audio").iterdir()) == []
    assert client.delete("/api/stories/999").status_code == 404


def test_tags_can_be_added_renamed_merged_and_removed(client):
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

    added = rename(kind="era", new=" Diwali 1998 ").json()  # no `old`: a new tag
    assert added["entities"]["era"] == ["1990s", "Diwali 1998"] and "Diwali 1998" in added["tags"]
    assert rename(kind="era", new="1990s").json()["entities"]["era"] == ["1990s", "Diwali 1998"]  # no duplicates


def test_memory_book_has_a_friendly_address(client):
    upload(client)
    assert "The Memory Book" in client.get("/book").text
    old = client.get("/api/book", follow_redirects=False)
    assert old.status_code == 308 and old.headers["location"] == "/book"


def test_sample_stories_can_be_removed_in_one_go(client):
    real = upload(client).json()["id"]
    sample = db.create_story(is_sample=True)
    db.update_story(sample, status="ready", transcript="a fictional story")
    assert client.delete("/api/samples").json() == {"removed": 1}
    assert [s["id"] for s in client.get("/api/stories").json()] == [real]


def test_health_shows_no_personal_paths(client, monkeypatch):
    from ghostwriter import selfcheck
    monkeypatch.setattr(main.selfcheck, "run_checks", selfcheck.run_checks)
    text = client.get("/api/health").text
    assert "Users" not in text and str(settings.models_dir) not in text


def test_settings_share_the_mood_list(client):
    assert client.get("/api/settings").json()["moods"] == ["joyful", "nostalgic", "loving", "poignant",
                                                           "mysterious", "eerie"]
