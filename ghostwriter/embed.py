"""Finding stories by meaning, not only by shared words.

EmbeddingGemma (run by the local Ollama, like Gemma itself) turns each story into a vector: a list of
numbers that places stories about similar things near each other. "Which relative was a good cook?"
then finds the kadhi story although no word matches. The vectors live in SQLite next to the stories.

It is optional: without the model the Seance falls back to keyword search alone.
"""

from __future__ import annotations

import array
import hashlib
import logging
import math
import threading
import time

import httpx

from ghostwriter import db
from ghostwriter.config import settings

log = logging.getLogger(__name__)

TIMEOUT = httpx.Timeout(120, connect=3)
DOC_CHARS = 1500  # of the transcript, after the title, summary and tags
BATCH = 8
_lock = threading.Lock()  # one backfill at a time
_down_until = 0.0  # after a failure, keyword search alone for a minute instead of waiting on every question


def document_text(story: dict) -> str:
    """What gets embedded for a story, in EmbeddingGemma's document format."""
    words = (story.get("transcript") or "")[:DOC_CHARS]
    return f"title: {story.get('title') or 'none'} | text: {story.get('summary') or ''} {story.get('tags') or ''}. {words}"


def query_text(question: str) -> str:
    return f"task: search result | query: {question}"


def _vectors(texts: list[str]) -> list[array.array] | None:
    """Unit-length vectors for `texts`, or None if the embedding model can't be reached."""
    global _down_until
    if time.monotonic() < _down_until:
        return None
    try:
        resp = httpx.post(f"{settings.ollama_url}/api/embed", timeout=TIMEOUT,
                          json={"model": settings.embed_model, "input": texts, "keep_alive": "20m"})
        resp.raise_for_status()
        raw = resp.json()["embeddings"]
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        log.info("meaning search unavailable (%s); using keywords only", exc)
        _down_until = time.monotonic() + 60
        return None
    out = []
    for vector in raw:
        norm = math.sqrt(sum(x * x for x in vector)) or 1.0
        out.append(array.array("f", (x / norm for x in vector)))
    return out


def _hash(text: str) -> str:
    return hashlib.sha256(f"{settings.embed_model}|{text}".encode()).hexdigest()[:16]


def refresh() -> int:
    """Embed every finished story whose vector is missing or out of date. Returns how many were embedded."""
    with _lock:
        with db.connect() as con:
            stories = [dict(r) for r in con.execute(
                f"""SELECT s.id, s.title, s.summary, s.tags, s.transcript, e.text_hash
                    FROM stories s LEFT JOIN embeddings e ON e.story_id = s.id
                    WHERE s.status = 'ready' AND s.{db.LIVE}""")]
        stale = [(s, document_text(s)) for s in stories]
        stale = [(s, text) for s, text in stale if s["text_hash"] != _hash(text)]
        done = 0
        for i in range(0, len(stale), BATCH):
            batch = stale[i:i + BATCH]
            vectors = _vectors([text for _, text in batch])
            if vectors is None:
                break
            with db.connect() as con:
                con.executemany(
                    "INSERT OR REPLACE INTO embeddings (story_id, model, text_hash, vector) VALUES (?, ?, ?, ?)",
                    [(s["id"], settings.embed_model, _hash(text), v.tobytes()) for (s, text), v in zip(batch, vectors)])
            done += len(batch)
        return done


def refresh_quietly() -> None:
    """For background threads: embed what's missing, never raise."""
    try:
        if n := refresh():
            log.info("embedded %d story(ies) for meaning search", n)
    except Exception:
        log.exception("embedding stories failed")


def similar(question: str) -> list[tuple[int, float]]:
    """Every embedded finished story with its similarity to the question (1 = same meaning), best first."""
    with db.connect() as con:
        rows = con.execute(
            f"""SELECT e.story_id, e.vector FROM embeddings e JOIN stories s ON s.id = e.story_id
                WHERE e.model = ? AND s.status = 'ready' AND s.{db.LIVE}""", (settings.embed_model,)).fetchall()
    if not rows:
        return []
    query = _vectors([query_text(question)])
    if query is None:
        return []
    q = query[0]
    scored = []
    for row in rows:
        v = array.array("f")
        v.frombytes(row["vector"])
        scored.append((row["story_id"], sum(a * b for a, b in zip(q, v))))
    return sorted(scored, key=lambda pair: -pair[1])
