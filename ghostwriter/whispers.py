"""Whispers: on launch the ghost sometimes murmurs a line from an old story, favouring faded ones.

No model is involved: the whisper is the storyteller's own words, picked from the transcript.
"""

from __future__ import annotations

import random
import re

from ghostwriter import db

SENTENCE_END = re.compile(r"(?<=[.!?।])\s+")  # । is the Devanagari full stop (danda)


def fragment(transcript: str, rng: random.Random = random) -> str | None:
    """One sentence of a readable length, or None if there isn't one."""
    sentences = [s.strip() for s in SENTENCE_END.split(transcript) if 5 <= len(s.split()) <= 30]
    return rng.choice(sentences) if sentences else None


def pick(rng: random.Random = random) -> dict | None:
    """A fragment from one of the three least recently visited finished stories."""
    with db.connect() as con:
        rows = con.execute(
            """SELECT id, title, transcript FROM stories
               WHERE status = 'ready' AND transcript IS NOT NULL
               ORDER BY last_visited_at ASC LIMIT 3"""
        ).fetchall()
    for row in rng.sample(rows, len(rows)):
        if text := fragment(row["transcript"], rng):
            return {"story_id": row["id"], "title": row["title"], "text": text}
    return None
