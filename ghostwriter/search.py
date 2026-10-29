"""Finding the stories that matter for a question: keywords (SQLite FTS5, BM25) and meaning (embed.py),
merged with reciprocal-rank fusion.

The question's meaningful words are OR-ed together. The trigram index matches them anywhere in a
story's title, summary, tags or transcript, in Hindi or English. Meaning search adds the stories that
say the same thing in other words. An answer to an earlier question counts as part of that story.
"""

from __future__ import annotations

import re

from ghostwriter import db, embed

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


# A keyword match scoring under half the best one is dropped: it rarely helps the answer, and every
# story Gemma has to read adds seconds on a CPU.
RELEVANCE = 0.5
# Meaning matches: EmbeddingGemma scored the right story 0.36-0.53 for real questions about the demo
# stories, and unrelated questions ("the capital of France", "hello") 0.17 at most.
MIN_SIMILARITY = 0.30
NEAR_BEST = 0.12  # and within this of the best meaning match
RRF_K = 60  # the usual constant for reciprocal-rank fusion


def keyword_matches(question: str, limit: int = 6) -> list[int]:
    """Finished stories matching the question's words, best first. Title and tag hits count most."""
    words = keywords(question)
    if not words:
        return []
    match = " OR ".join(f'"{w}"' for w in words)  # quoted, so words are never read as FTS syntax
    with db.connect() as con:
        rows = con.execute(
            f"""SELECT s.id, bm25(stories_fts, 3.0, 2.0, 3.0, 1.0) AS score  -- title, summary, tags, transcript
               FROM stories_fts JOIN stories s ON s.id = stories_fts.rowid
               WHERE stories_fts MATCH ? AND s.status = 'ready' AND s.{db.LIVE}
               ORDER BY score
               LIMIT ?""",
            (match, limit),
        ).fetchall()
    # bm25 scores are negative: the lower, the better.
    return [r["id"] for r in rows if r["score"] <= rows[0]["score"] * RELEVANCE]


def meaning_matches(question: str) -> list[int]:
    scored = embed.similar(question)
    if not scored or scored[0][1] < MIN_SIMILARITY:
        return []
    best = scored[0][1]
    return [i for i, sim in scored if sim >= MIN_SIMILARITY and sim >= best - NEAR_BEST]


def fuse(*rankings: list[int]) -> list[int]:
    """Reciprocal-rank fusion: a story near the top of either list rises; one in both rises most."""
    score: dict[int, float] = {}
    for ranking in rankings:
        for rank, story_id in enumerate(ranking):
            score[story_id] = score.get(story_id, 0) + 1 / (RRF_K + rank + 1)
    return sorted(score, key=lambda i: -score[i])


def find_stories(question: str, limit: int = 3) -> list[dict]:
    """The best-matching finished stories, each with the answers added to it later."""
    ranked = fuse(keyword_matches(question), meaning_matches(question))
    with db.connect() as con:
        parents = {r["id"]: r["parent"] for r in con.execute(
            f"""SELECT s.id, q.story_id AS parent FROM stories s LEFT JOIN questions q ON q.id = s.answers_question_id
                WHERE s.id IN ({", ".join("?" * len(ranked))})""", ranked)} if ranked else {}
    ids = list(dict.fromkeys(parents.get(i) or i for i in ranked))[:limit]  # an answer leads to its story
    return [s for s in (_with_answers(i) for i in ids) if s]


def _with_answers(story_id: int) -> dict | None:
    story = db.get_story(story_id)
    if not story or story["status"] != "ready":
        return None
    story["added_later"] = [(q["text"], q["answer"]) for q in story["questions"]
                            if q["answer"] and q["answer"]["status"] == "ready"]
    return story
