"""Sample seeding and the text-only pipeline path, with Gemma mocked."""

from ghostwriter import db, llm, samples


def test_samples_are_analysed_once_and_marked(data_dir, analysis, monkeypatch):
    seen = []

    def fake_analyse(transcript, answering=None):
        seen.append(transcript)
        return analysis

    monkeypatch.setattr(llm, "analyse_story", fake_analyse)

    ids = samples.seed()
    assert len(ids) == 4
    assert all(db.get_story(i)["status"] == "ready" and db.get_story(i)["is_sample"] for i in ids)
    assert any("दादी" in t or "नानी" in t for t in seen)  # Hindi transcripts pass through intact
    visits = [db.get_story(i)["last_visited_at"] for i in ids]
    assert visits == sorted(visits, reverse=True) and len(set(visits)) == 4  # each fades a bit more

    assert samples.seed() == []  # running it again adds nothing
