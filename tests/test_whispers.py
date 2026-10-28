"""Whisper tests: fragment selection works for English and Hindi, and favours faded stories."""

import random

from ghostwriter import db, whispers
from tests.test_search import add_story


def test_fragment_picks_a_readable_sentence_in_either_script():
    assert whispers.fragment("Hi. The clock stopped at exactly eleven that night. Bye.") == \
        "The clock stopped at exactly eleven that night."
    hindi = "नानी की कढ़ी पूरे लखनऊ में मशहूर थी। हाँ।"
    assert whispers.fragment(hindi) == "नानी की कढ़ी पूरे लखनऊ में मशहूर थी।"
    assert whispers.fragment("Too short.") is None


def test_whispers_come_from_the_most_faded_stories(data_dir):
    ids = [add_story(f"Story {n}", f"This is the remembered line number {n} of a story.") for n in range(5)]
    for n, story_id in enumerate(ids):
        db.update_story(story_id, last_visited_at=f"2026-10-0{n + 1} 00:00:00")

    picked = {whispers.pick(random.Random(seed))["story_id"] for seed in range(30)}
    assert picked == set(ids[:3])


def test_empty_archive_has_nothing_to_whisper(data_dir):
    assert whispers.pick() is None
