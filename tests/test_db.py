"""Database tests: storage round-trip, full-text index, follow-up links, crash recovery."""

from ghostwriter import db


def fts_ids(query: str) -> list[int]:
    with db.connect() as con:
        return [r[0] for r in con.execute("SELECT rowid FROM stories_fts WHERE stories_fts MATCH ?", (query,))]


def test_analysis_round_trip(data_dir, analysis):
    story_id = db.create_story()
    db.update_story(story_id, transcript="दादी हर दिवाली पर दीया जलाती थीं", language="hi")
    db.save_analysis(story_id, analysis)

    story = db.get_story(story_id)
    assert story["status"] == "ready"
    assert story["title"] == analysis.title
    assert story["entities"]["person"] == ["Dadi (grandmother)"]
    assert story["entities"]["keepsake"] == ["brass lamp"]
    assert [q["text"] for q in story["questions"]] == analysis.unfinished_business


def test_fts_finds_hindi_and_english_substrings(data_dir, analysis):
    story_id = db.create_story()
    db.update_story(story_id, transcript="दादी हर दिवाली पर दीया जलाती थीं")
    db.save_analysis(story_id, analysis)  # title/summary update must re-index too

    assert fts_ids('"दिवाली"') == [story_id]
    assert fts_ids('"lamp"') == [story_id]
    assert fts_ids('"terra"') == [story_id]  # trigram: substring of "Terrace"
    assert fts_ids('"zombie"') == []


def test_deleting_a_story_removes_it_from_the_index(data_dir):
    story_id = db.create_story()
    db.update_story(story_id, transcript="the haunted peepal tree")
    db.delete_story(story_id)
    assert fts_ids('"peepal"') == []


def test_answer_links_back_to_its_question(data_dir, analysis):
    story_id = db.create_story()
    db.save_analysis(story_id, analysis)
    question_id = db.get_story(story_id)["questions"][0]["id"]

    answer_id = db.create_story(answers_question_id=question_id)

    assert db.get_story(story_id)["questions"][0]["answered_by"] == answer_id
    assert db.get_story(answer_id)["answers"]["story_id"] == story_id


def test_interrupted_stories_become_retryable(data_dir):
    stuck = db.create_story()
    db.update_story(stuck, status="transcribing")
    done = db.create_story()
    db.update_story(done, status="ready")

    assert db.mark_interrupted() == 1
    assert db.get_story(stuck)["status"] == "failed"
    assert db.get_story(done)["status"] == "ready"


def test_update_story_rejects_unknown_columns(data_dir):
    import pytest

    with pytest.raises(ValueError):
        db.update_story(db.create_story(), id=99)
