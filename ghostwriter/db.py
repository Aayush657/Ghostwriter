"""SQLite storage: stories, what Gemma found in them, follow-up questions, and a full-text index.

Everything is one file on disk (data/ghostwriter.db). Each call opens its own short-lived
connection, which keeps it safe to use from FastAPI's worker threads without a pool.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from ghostwriter.config import settings
from ghostwriter.models import StoryAnalysis

TABLES = """
CREATE TABLE IF NOT EXISTS stories (
    id                  INTEGER PRIMARY KEY,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    last_visited_at     TEXT NOT NULL DEFAULT (datetime('now')),
    status              TEXT NOT NULL DEFAULT 'queued',  -- queued|transcribing|thinking|ready|failed
    error               TEXT,
    answers_question_id INTEGER REFERENCES questions(id), -- set when this recording answers one
    audio_original      TEXT,   -- paths are relative to the data folder
    audio_wav           TEXT,
    duration_s          REAL,
    language            TEXT,
    transcript          TEXT,
    title               TEXT,
    summary             TEXT,
    mood                TEXT,
    tags                TEXT,   -- people, places, eras, keepsakes as one searchable line
    reaction            TEXT,   -- the Archivist's first words about the story
    retelling           TEXT,   -- the story retold as a ghost story (the original is never changed)
    is_sample           INTEGER NOT NULL DEFAULT 0  -- 1 for the fictional demo stories
);

CREATE TABLE IF NOT EXISTS entities (
    story_id INTEGER NOT NULL REFERENCES stories(id) ON DELETE CASCADE,
    kind     TEXT NOT NULL,  -- person|place|era|keepsake
    value    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS entities_by_kind ON entities(kind, value);

-- "Unfinished business": gaps the ghost noticed in a story.
CREATE TABLE IF NOT EXISTS questions (
    id       INTEGER PRIMARY KEY,
    story_id INTEGER NOT NULL REFERENCES stories(id) ON DELETE CASCADE,
    text     TEXT NOT NULL
);
"""

# Full-text index over the stories table. 'trigram' matches substrings in any script,
# so Hindi (Devanagari) and English both work, and "haunt" also finds "haunted".
# Tags make names searchable in Latin script even when the transcript is in Devanagari.
# Triggers keep the index in step with the table.
SEARCH_INDEX = """
CREATE VIRTUAL TABLE IF NOT EXISTS stories_fts USING fts5(
    title, summary, tags, transcript,
    content='stories', content_rowid='id', tokenize='trigram'
);
CREATE TRIGGER IF NOT EXISTS stories_fts_insert AFTER INSERT ON stories BEGIN
    INSERT INTO stories_fts(rowid, title, summary, tags, transcript)
    VALUES (new.id, new.title, new.summary, new.tags, new.transcript);
END;
CREATE TRIGGER IF NOT EXISTS stories_fts_delete AFTER DELETE ON stories BEGIN
    INSERT INTO stories_fts(stories_fts, rowid, title, summary, tags, transcript)
    VALUES ('delete', old.id, old.title, old.summary, old.tags, old.transcript);
END;
CREATE TRIGGER IF NOT EXISTS stories_fts_update AFTER UPDATE OF title, summary, tags, transcript ON stories BEGIN
    INSERT INTO stories_fts(stories_fts, rowid, title, summary, tags, transcript)
    VALUES ('delete', old.id, old.title, old.summary, old.tags, old.transcript);
    INSERT INTO stories_fts(rowid, title, summary, tags, transcript)
    VALUES (new.id, new.title, new.summary, new.tags, new.transcript);
END;
"""
SEARCH_COLUMNS = ["title", "summary", "tags", "transcript"]

# Columns added after a database may already exist. init_db() adds any that are missing.
ADDED_COLUMNS = {"reaction": "TEXT", "is_sample": "INTEGER NOT NULL DEFAULT 0", "tags": "TEXT",
                 "retelling": "TEXT"}

# Columns update_story() may touch. Column names can't be SQL parameters, so we whitelist them.
UPDATABLE = {"status", "error", "audio_original", "audio_wav", "duration_s", "language",
             "transcript", "last_visited_at", "reaction", "retelling"}

ENTITY_KINDS = {"people": "person", "places": "place", "eras": "era", "keepsakes": "keepsake"}

IN_PROGRESS = ("queued", "transcribing", "thinking")


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """Open a connection; commit if the block succeeds, roll back if it raises."""
    con = sqlite3.connect(settings.db_path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        with con:
            yield con
    finally:
        con.close()


def init_db() -> None:
    """Create the data folders and tables if they don't exist yet. Safe to run every start."""
    (settings.data_dir / "audio").mkdir(parents=True, exist_ok=True)
    with connect() as con:
        con.execute("PRAGMA journal_mode = WAL")  # readers don't block the background writer
        con.executescript(TABLES)
        existing = {row["name"] for row in con.execute("PRAGMA table_info(stories)")}
        for name, sql_type in ADDED_COLUMNS.items():
            if name not in existing:
                con.execute(f"ALTER TABLE stories ADD COLUMN {name} {sql_type}")
        _upgrade_search_index(con)


def _upgrade_search_index(con: sqlite3.Connection) -> None:
    """Create the search index, or rebuild it if an older version has different columns.

    The index only mirrors the stories table, so dropping and rebuilding it loses nothing.
    """
    indexed = [row["name"] for row in con.execute("PRAGMA table_info(stories_fts)")]
    if indexed == SEARCH_COLUMNS:
        return
    if indexed:
        con.execute("DROP TABLE stories_fts")
        for trigger in ("insert", "delete", "update"):
            con.execute(f"DROP TRIGGER IF EXISTS stories_fts_{trigger}")
    # Stories saved before tags existed get them from the entities table.
    con.execute("""UPDATE stories SET tags =
                       (SELECT group_concat(value, ' · ') FROM entities WHERE story_id = stories.id)
                   WHERE tags IS NULL""")
    con.executescript(SEARCH_INDEX)
    con.execute("INSERT INTO stories_fts(stories_fts) VALUES ('rebuild')")


def create_story(answers_question_id: int | None = None, is_sample: bool = False) -> int:
    with connect() as con:
        cur = con.execute("INSERT INTO stories (answers_question_id, is_sample) VALUES (?, ?)",
                          (answers_question_id, int(is_sample)))
        return cur.lastrowid


def update_story(story_id: int, **fields: Any) -> None:
    unknown = fields.keys() - UPDATABLE
    if unknown:
        raise ValueError(f"not updatable: {sorted(unknown)}")
    assignments = ", ".join(f"{name} = ?" for name in fields)
    with connect() as con:
        con.execute(f"UPDATE stories SET {assignments} WHERE id = ?", (*fields.values(), story_id))


def delete_story(story_id: int) -> None:
    with connect() as con:
        con.execute("DELETE FROM stories WHERE id = ?", (story_id,))


def save_analysis(story_id: int, analysis: StoryAnalysis) -> None:
    """Store Gemma's findings and mark the story ready, all in one transaction."""
    tags = " · ".join(v.strip() for field in ENTITY_KINDS for v in getattr(analysis, field) if v.strip())
    with connect() as con:
        con.execute(
            "UPDATE stories SET title = ?, summary = ?, mood = ?, tags = ?, status = 'ready', error = NULL "
            "WHERE id = ?",
            (analysis.title, analysis.summary, analysis.mood, tags, story_id),
        )
        con.execute("DELETE FROM entities WHERE story_id = ?", (story_id,))
        con.execute("DELETE FROM questions WHERE story_id = ?", (story_id,))
        for field, kind in ENTITY_KINDS.items():
            con.executemany(
                "INSERT INTO entities (story_id, kind, value) VALUES (?, ?, ?)",
                [(story_id, kind, value.strip()) for value in getattr(analysis, field) if value.strip()],
            )
        con.executemany(
            "INSERT INTO questions (story_id, text) VALUES (?, ?)",
            [(story_id, q) for q in analysis.unfinished_business],
        )


def get_story(story_id: int) -> dict | None:
    """One story with its entities (grouped by kind) and its follow-up questions."""
    with connect() as con:
        row = con.execute("SELECT * FROM stories WHERE id = ?", (story_id,)).fetchone()
        if row is None:
            return None
        story = dict(row)
        story["entities"] = _entities(con, [story_id]).get(story_id, {})
        story["questions"] = [dict(q) for q in con.execute(
            """SELECT q.id, q.text,
                      (SELECT max(a.id) FROM stories a WHERE a.answers_question_id = q.id) AS answered_by
               FROM questions q WHERE q.story_id = ? ORDER BY q.id""",
            (story_id,),
        )]
        if story["answers_question_id"]:
            story["answers"] = dict(con.execute(
                "SELECT id, story_id, text FROM questions WHERE id = ?", (story["answers_question_id"],)
            ).fetchone())
        return story


def list_stories() -> list[dict]:
    """All stories, newest first, without the long transcript."""
    with connect() as con:
        rows = [dict(r) for r in con.execute(
            """SELECT id, created_at, last_visited_at, status, error, title, summary, mood,
                      duration_s, language, answers_question_id, is_sample
               FROM stories ORDER BY created_at DESC, id DESC"""
        )]
        entities = _entities(con, [r["id"] for r in rows])
        for r in rows:
            r["entities"] = entities.get(r["id"], {})
        return rows


def question_exists(question_id: int) -> bool:
    with connect() as con:
        return con.execute("SELECT 1 FROM questions WHERE id = ?", (question_id,)).fetchone() is not None


def mark_interrupted() -> int:
    """Stories left mid-processing by a crash or restart become 'failed' so they can be retried."""
    placeholders = ", ".join("?" for _ in IN_PROGRESS)
    with connect() as con:
        cur = con.execute(
            f"UPDATE stories SET status = 'failed', error = 'Interrupted before it finished. Try again.' "
            f"WHERE status IN ({placeholders})",
            IN_PROGRESS,
        )
        return cur.rowcount


def _entities(con: sqlite3.Connection, story_ids: list[int]) -> dict[int, dict[str, list[str]]]:
    """{story_id: {"person": [...], "place": [...], ...}} for the given stories."""
    if not story_ids:
        return {}
    placeholders = ", ".join("?" for _ in story_ids)
    grouped: dict[int, dict[str, list[str]]] = {}
    for r in con.execute(
        f"SELECT story_id, kind, value FROM entities WHERE story_id IN ({placeholders}) ORDER BY rowid",
        story_ids,
    ):
        grouped.setdefault(r["story_id"], {}).setdefault(r["kind"], []).append(r["value"])
    return grouped
