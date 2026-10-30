"""Sample seeding and the text-only pipeline path, with Gemma mocked."""

from ghostwriter import db, llm, samples


def test_samples_are_analysed_once_and_marked(data_dir, analysis, monkeypatch):
    seen = []

    def fake_analyse(transcript, answering=None):
        seen.append(transcript)
        return analysis

    monkeypatch.setattr(llm, "analyse_story", fake_analyse)
    monkeypatch.setattr(llm, "write_note", lambda story: f"A note about {story['title']}.")
    monkeypatch.setattr(llm, "unanswered_questions", lambda transcript, analysis, answering=None: analysis.unfinished_business)

    ids = samples.seed()
    assert len(ids) == 2
    assert all(db.get_story(i)["status"] == "ready" and db.get_story(i)["is_sample"] for i in ids)
    assert db.get_story(ids[0])["reaction"].startswith("A note about")  # written during processing
    assert any("Camp Wahkeena" in t for t in seen) and any("Old Hollis" in t for t in seen)  # campfire stories
    visits = [db.get_story(i)["last_visited_at"] for i in ids]
    assert visits == sorted(visits, reverse=True) and len(set(visits)) == 2  # the second fades more

    assert samples.seed() == []  # running it again adds nothing


def test_a_note_that_fails_never_fails_the_story(data_dir, analysis, monkeypatch):
    from ghostwriter import pipeline

    def no_gemma(story):
        raise llm.LLMError("Ollama isn't running.")

    monkeypatch.setattr(llm, "analyse_story", lambda transcript, answering=None: analysis)
    monkeypatch.setattr(llm, "write_note", no_gemma)
    monkeypatch.setattr(llm, "unanswered_questions", lambda transcript, analysis, answering=None: analysis.unfinished_business)
    story_id = db.create_story()
    db.update_story(story_id, transcript="a story")

    pipeline.process_story(story_id)

    story = db.get_story(story_id)
    assert story["status"] == "ready" and story["reaction"] is None  # the page writes it when opened
