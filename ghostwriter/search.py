"""Finding the stories that matter for a question, with SQLite FTS5 and BM25 ranking.

The question's meaningful words are OR-ed together. The trigram index matches them anywhere
in a story's title, summary or transcript, in Hindi or English.
"""

from __future__ import annotations

import re

from ghostwriter import db

# Words that say nothing about *which* story you mean (English, Hinglish and Hindi).
STOPWORDS = set("""
a about after again all also am an and any are as at be been before but by can could did do does
doing for from had has have he her here him his how i if in into is it its just know me more most my
no not of on once only or other our out over please remember said say she should so some story
stories tell than that the their them then there these they this those through to told too under
until up us very was we were what when where which while who whom why will with would you your
kya kaun kab kahan kaise kyun tha thi the hai hain mein main aur nahi kuch bata batao mujhe mera meri
kabhi wala wali
क्या कौन कब कहाँ कैसे क्यों था थी थे है हैं में और नहीं कुछ बताओ मुझे मेरा मेरी
""".split())

# Split on whitespace and punctuation only. (Python's \\w would break Hindi words apart,
# because Devanagari vowel signs are not "word" characters.)
_SPLIT = re.compile(r"""[\s.,!?;:"'()\[\]{}<>/\\|।॥-]+""")


def keywords(question: str) -> list[str]:
    """Meaningful words of at least 3 characters (the trigram index can't match shorter ones)."""
    words = [w for w in _SPLIT.split(question.lower()) if len(w) >= 3 and w not in STOPWORDS]
    return list(dict.fromkeys(words))  # de-duplicate, keep order


# A match scoring under half the best one is dropped: it rarely helps the answer, and every story
# Gemma has to read adds seconds on a CPU.
RELEVANCE = 0.5


def find_stories(question: str, limit: int = 3) -> list[dict]:
    """The best-matching finished stories. Title and tag hits count most, then summary, then transcript."""
    words = keywords(question)
    if not words:
        return []
    match = " OR ".join(f'"{w}"' for w in words)  # quoted, so words are never read as FTS syntax
    with db.connect() as con:
        rows = [dict(r) for r in con.execute(
            """SELECT s.id, s.title, s.summary, s.tags, s.transcript,
                      bm25(stories_fts, 3.0, 2.0, 3.0, 1.0) AS score  -- title, summary, tags, transcript
               FROM stories_fts JOIN stories s ON s.id = stories_fts.rowid
               WHERE stories_fts MATCH ? AND s.status = 'ready'
               ORDER BY score
               LIMIT ?""",
            (match, limit),
        )]
    # bm25 scores are negative: the lower, the better.
    return [r for r in rows if r["score"] <= rows[0]["score"] * RELEVANCE]
