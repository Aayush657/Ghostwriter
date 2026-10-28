"""Search tests: keyword extraction (Hindi kept whole) and BM25 retrieval over the FTS index."""

from ghostwriter import db, search
from ghostwriter.models import StoryAnalysis


def add_story(title: str, transcript: str, status: str = "ready") -> int:
    story_id = db.create_story()
    db.update_story(story_id, transcript=transcript)
    db.save_analysis(story_id, StoryAnalysis(
        title=title, summary="A remembered evening.", people=[], places=[], eras=[], mood="calm",
        keepsakes=[], unfinished_business=["What next?", "Who else was there?"]))
    if status != "ready":
        db.update_story(story_id, status=status)
    return story_id


def test_keywords_drop_filler_and_keep_hindi_words_whole():
    assert search.keywords("What did Dadi cook on Diwali?") == ["dadi", "cook", "diwali"]
    assert search.keywords("दादी ने गुझिया कब बनाई?") == ["दादी", "गुझिया", "बनाई"]
    assert search.keywords("tell me a story") == []


def test_title_matches_outrank_transcript_matches(data_dir):
    in_transcript = add_story("A Hostel Night", "and somewhere a clock was ticking")
    in_title = add_story("The Clock That Listened", "every night it stopped")
    assert [s["id"] for s in search.find_stories("the clock")] == [in_title, in_transcript]


def test_unfinished_stories_are_not_searched(data_dir):
    add_story("The Clock That Listened", "tick tock", status="thinking")
    assert search.find_stories("clock") == []


def test_fts_syntax_in_questions_is_harmless(data_dir):
    add_story("The Clock", "tick")
    assert search.find_stories('clock" OR "*') != []  # quotes are split off, never parsed as FTS syntax
