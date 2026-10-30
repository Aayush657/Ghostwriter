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
from ghostwriter.models import MOODS, StoryAnalysis, normalise_mood

TABLES = """
CREATE TABLE IF NOT EXISTS stories (
    id                  INTEGER PRIMARY KEY,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    last_visited_at     TEXT NOT NULL DEFAULT (datetime('now')),
    status              TEXT NOT NULL DEFAULT 'queued',  -- queued|transcribing|thinking|noting|ready|failed|unclear
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

-- What each story means, as a vector, so the Seance can find it by meaning (see embed.py).
CREATE TABLE IF NOT EXISTS embeddings (
    story_id  INTEGER PRIMARY KEY REFERENCES stories(id) ON DELETE CASCADE,
    model     TEXT NOT NULL,
    text_hash TEXT NOT NULL,  -- the embedded text changed (re-read, edited): embed it again
    vector    BLOB NOT NULL   -- float32
);

-- How long each step took on this computer, so the page can say how long the next one will take.
CREATE TABLE IF NOT EXISTS timings (
    id      INTEGER PRIMARY KEY,
    step    TEXT NOT NULL,  -- transcribing|thinking|noting
    audio_s REAL,
    seconds REAL NOT NULL
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
                 "retelling": "TEXT",
                 "transcript_original": "TEXT",  # Whisper's words, kept the first time someone edits them
                 "language_choice": "TEXT",       # unused since Ghostwriter became English-only; kept for old data
                 "language_probability": "REAL",  # unused likewise
                 "quality": "TEXT",               # JSON: Whisper's confidence figures (transcribe.Quality)
                 "uncertain": "INTEGER NOT NULL DEFAULT 0",  # Gemma left out words it couldn't make sense of
                 "error_kind": "TEXT",            # transient (try again) | audio (choose another file)
                 "started_at": "TEXT",            # processing began (UTC), for the page's clock
                 "stage_at": "TEXT",              # the current step began (UTC), for the time-left estimate
                 "deleted_at": "TEXT",            # deleted, but can still be undone for a few seconds
                 "written": "INTEGER NOT NULL DEFAULT 0"}  # typed by the storyteller instead of recorded

# Columns update_story() may touch. Column names can't be SQL parameters, so we whitelist them.
UPDATABLE = {"status", "error", "error_kind", "audio_original", "audio_wav", "duration_s", "language", "title",
             "transcript", "transcript_original", "last_visited_at", "reaction", "retelling", "mood",
             "quality", "started_at", "stage_at"}

ENTITY_KINDS = {"people": "person", "places": "place", "eras": "era", "keepsakes": "keepsake"}

IN_PROGRESS = ("queued", "transcribing", "thinking", "noting")
# Not deleted (a deleted story waits a few seconds for an Undo, then is purged).
LIVE = "deleted_at IS NULL"


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
        _fix_moods(con)


def _fix_moods(con: sqlite3.Connection) -> None:
    """Moods from before the fixed list ("confused", "calm") become the nearest candle mood."""
    placeholders = ", ".join("?" for _ in MOODS)
    for row in con.execute(f"SELECT id, mood FROM stories WHERE mood IS NOT NULL AND mood NOT IN ({placeholders})",
                           MOODS).fetchall():
        con.execute("UPDATE stories SET mood = ? WHERE id = ?", (normalise_mood(row["mood"]), row["id"]))


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


class AlreadyAnswered(Exception):
    """The question already has an answer; it must be removed before another is given."""


def create_story(answers_question_id: int | None = None, is_sample: bool = False, written: bool = False) -> int:
    with connect() as con:
        # One statement, so two answers sent at the same moment can't both get in (WAL refuses the stale one).
        cur = con.execute(
            "INSERT INTO stories (answers_question_id, is_sample, written) SELECT ?, ?, ? WHERE ? IS NULL OR NOT EXISTS "
            f"(SELECT 1 FROM stories WHERE answers_question_id = ? AND {LIVE})",
            (answers_question_id, int(is_sample), int(written), answers_question_id, answers_question_id))
        if cur.rowcount == 0:
            raise AlreadyAnswered
        return cur.lastrowid


def update_story(story_id: int, **fields: Any) -> None:
    unknown = fields.keys() - UPDATABLE
    if unknown:
        raise ValueError(f"not updatable: {sorted(unknown)}")
    assignments = ", ".join(f"{name} = ?" for name in fields)
    with connect() as con:
        con.execute(f"UPDATE stories SET {assignments} WHERE id = ?", (*fields.values(), story_id))


def answer_ids(story_id: int) -> list[int]:
    """The recordings that answered this story's questions ("added later")."""
    with connect() as con:
        return [r["id"] for r in con.execute(
            "SELECT id FROM stories WHERE answers_question_id IN (SELECT id FROM questions WHERE story_id = ?)",
            (story_id,))]


def delete_story(story_id: int) -> None:
    """Remove a story with its tags, questions and answers (the search index follows through its trigger).

    trash.py calls this a few seconds after the visitor deletes a story, so the deletion can be undone.
    """
    with connect() as con:
        con.execute("DELETE FROM stories WHERE answers_question_id IN "
                    "(SELECT id FROM questions WHERE story_id = ?)", (story_id,))
        con.execute("DELETE FROM stories WHERE id = ?", (story_id,))


def set_deleted(story_ids: list[int], deleted: bool) -> None:
    placeholders = ", ".join("?" for _ in story_ids)
    when = "datetime('now')" if deleted else "NULL"
    with connect() as con:
        con.execute(f"UPDATE stories SET deleted_at = {when} WHERE id IN ({placeholders})", story_ids)


def deleted_before(seconds: float) -> list[int]:
    """Stories deleted at least `seconds` ago: their Undo has run out."""
    with connect() as con:
        return [r["id"] for r in con.execute(
            "SELECT id FROM stories WHERE deleted_at IS NOT NULL AND deleted_at <= datetime('now', ?)",
            (f"-{seconds} seconds",))]


def save_analysis(story_id: int, analysis: StoryAnalysis, status: str = "ready") -> None:
    """Store Gemma's findings and set the story's status, all in one transaction.

    Questions that were already answered by another recording are kept, with their answers.
    """
    tags = " · ".join(v.strip() for field in ENTITY_KINDS for v in getattr(analysis, field) if v.strip())
    with connect() as con:
        con.execute(
            "UPDATE stories SET title = ?, summary = ?, mood = ?, tags = ?, uncertain = ?, status = ?, "
            "error = NULL, error_kind = NULL WHERE id = ?",
            (analysis.title, analysis.summary, analysis.mood, tags, int(analysis.uncertain), status, story_id),
        )
        con.execute("DELETE FROM entities WHERE story_id = ?", (story_id,))
        con.execute("DELETE FROM questions WHERE story_id = ? AND id NOT IN "
                    "(SELECT answers_question_id FROM stories WHERE answers_question_id IS NOT NULL)", (story_id,))
        for field, kind in ENTITY_KINDS.items():
            con.executemany(
                "INSERT INTO entities (story_id, kind, value) VALUES (?, ?, ?)",
                [(story_id, kind, value.strip()) for value in getattr(analysis, field) if value.strip()],
            )
        kept = {r["text"].strip().lower() for r in con.execute("SELECT text FROM questions WHERE story_id = ?",
                                                                 (story_id,))}
        con.executemany(  # a question asked again on a re-read isn't added twice next to its answer
            "INSERT INTO questions (story_id, text) VALUES (?, ?)",
            [(story_id, q) for q in analysis.unfinished_business if q.strip().lower() not in kept],
        )


def clear_reading(story_id: int) -> None:
    """Forget what Gemma wrote about a story (its words were unclear, or are being heard again).

    Answered questions stay, with their answers.
    """
    with connect() as con:
        con.execute("UPDATE stories SET title = NULL, summary = NULL, mood = NULL, tags = NULL, reaction = NULL, "
                    "uncertain = 0 WHERE id = ?", (story_id,))
        con.execute("DELETE FROM entities WHERE story_id = ?", (story_id,))
        con.execute("DELETE FROM questions WHERE story_id = ? AND id NOT IN "
                    "(SELECT answers_question_id FROM stories WHERE answers_question_id IS NOT NULL)", (story_id,))


# What the story page shows of an answer, inside the story it belongs to.
ANSWER_FIELDS = ("id, created_at, status, error, error_kind, title, summary, transcript, audio_original, "
                 "written, quality, duration_s, started_at")


def get_story(story_id: int, include_deleted: bool = False) -> dict | None:
    """One story with its entities (grouped by kind), its follow-up questions and their answers."""
    with connect() as con:
        row = con.execute("SELECT * FROM stories WHERE id = ?" + ("" if include_deleted else f" AND {LIVE}"),
                          (story_id,)).fetchone()
        if row is None:
            return None
        story = dict(row)
        story["entities"] = _entities(con, [story_id]).get(story_id, {})
        story["questions"] = [dict(q) for q in con.execute(
            f"""SELECT q.id, q.text,
                      (SELECT max(a.id) FROM stories a WHERE a.answers_question_id = q.id AND a.{LIVE}) AS answered_by
               FROM questions q WHERE q.story_id = ? ORDER BY q.id""",
            (story_id,),
        )]
        for q in story["questions"]:
            answer = q["answered_by"] and con.execute(
                f"SELECT {ANSWER_FIELDS} FROM stories WHERE id = ?", (q["answered_by"],)).fetchone()
            q["answer"] = dict(answer) if answer else None
        if story["answers_question_id"]:
            story["answers"] = dict(con.execute(
                "SELECT q.id, q.story_id, q.text, s.title AS story_title, s.summary AS story_summary "
                "FROM questions q JOIN stories s ON s.id = q.story_id WHERE q.id = ?",
                (story["answers_question_id"],),
            ).fetchone())
        return story


def list_stories() -> list[dict]:
    """All stories, newest first, without the long transcript.

    An answer to an earlier question has a `parent_id`: the page shows it inside that story, not on the wall.
    """
    with connect() as con:
        rows = [dict(r) for r in con.execute(
            f"""SELECT id, created_at, last_visited_at, status, error, title, summary, mood,
                      duration_s, language, answers_question_id, is_sample,
                      (SELECT story_id FROM questions WHERE id = answers_question_id) AS parent_id
               FROM stories WHERE {LIVE} ORDER BY created_at DESC, id DESC"""
        )]
        entities = _entities(con, [r["id"] for r in rows])
        for r in rows:
            r["entities"] = entities.get(r["id"], {})
        return rows


def rename_tag(story_id: int, kind: str, old: str, new: str) -> bool:
    """Rename one of a story's tags. Renaming to a tag it already has merges the two; "" removes it.
    An empty `old` adds `new` as a new tag.

    Only this story changes: "grandmother" in one story may be Nani, in another Dadi.
    Tags match whatever their case ("SON" is "son"); the spelling already there is kept. Returns False
    if `old` isn't one of the story's tags.
    """
    new, old = new.strip(), old.strip()
    with connect() as con:
        same = "story_id = ? AND kind = ? AND value = ? COLLATE NOCASE"
        if old and not con.execute(f"SELECT 1 FROM entities WHERE {same}", (story_id, kind, old)).fetchone():
            return False
        exists = new and new.lower() != old.lower() and con.execute(
            f"SELECT 1 FROM entities WHERE {same}", (story_id, kind, new)).fetchone()
        if not old:
            if new and not con.execute(f"SELECT 1 FROM entities WHERE {same}", (story_id, kind, new)).fetchone():
                con.execute("INSERT INTO entities (story_id, kind, value) VALUES (?, ?, ?)", (story_id, kind, new))
        elif not new or exists:
            con.execute(f"DELETE FROM entities WHERE {same}", (story_id, kind, old))
        else:
            con.execute(f"UPDATE entities SET value = ? WHERE {same}", (new, story_id, kind, old))
        con.execute("UPDATE stories SET tags = (SELECT group_concat(value, ' · ') FROM entities "
                    "WHERE story_id = ?) WHERE id = ?", (story_id, story_id))
    return True


def live_answer(question_id: int) -> int | None:
    """The id of the answer a question has now, if any."""
    with connect() as con:
        row = con.execute(f"SELECT id FROM stories WHERE answers_question_id = ? AND {LIVE}", (question_id,)).fetchone()
        return row["id"] if row else None


def question_exists(question_id: int) -> bool:
    with connect() as con:
        return con.execute("SELECT 1 FROM questions WHERE id = ?", (question_id,)).fetchone() is not None


def mark_interrupted() -> int:
    """Stories left mid-processing by a crash or restart become 'failed' so they can be retried."""
    placeholders = ", ".join("?" for _ in IN_PROGRESS)
    with connect() as con:
        cur = con.execute(
            f"UPDATE stories SET status = 'failed', error_kind = 'transient', "
            f"error = 'Interrupted before it finished. Try again.' "
            f"WHERE status IN ({placeholders})",
            IN_PROGRESS,
        )
        return cur.rowcount


def known_names(limit: int = 40) -> list[str]:
    """People, places and keepsakes already in the archive, most mentioned first (Whisper's vocabulary)."""
    with connect() as con:
        return [r["value"] for r in con.execute(
            f"""SELECT e.value FROM entities e JOIN stories s ON s.id = e.story_id
               WHERE e.kind IN ('person', 'place', 'keepsake') AND s.{LIVE}
               GROUP BY lower(e.value) ORDER BY count(*) DESC, max(e.rowid) DESC LIMIT ?""", (limit,))]


def record_timing(step: str, seconds: float, audio_s: float | None = None) -> None:
    """Remember how long a step took (the last 20 of each kind are kept)."""
    with connect() as con:
        con.execute("INSERT INTO timings (step, audio_s, seconds) VALUES (?, ?, ?)", (step, audio_s, seconds))
        con.execute("DELETE FROM timings WHERE step = ? AND id NOT IN "
                    "(SELECT id FROM timings WHERE step = ? ORDER BY id DESC LIMIT 20)", (step, step))


def timings(step: str) -> list[tuple[float | None, float]]:
    """(audio seconds, seconds taken) for the recent runs of one step, newest first."""
    with connect() as con:
        return [(r["audio_s"], r["seconds"]) for r in con.execute(
            "SELECT audio_s, seconds FROM timings WHERE step = ? ORDER BY id DESC", (step,))]


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
