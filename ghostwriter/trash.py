"""Deleting stories, with a short Undo.

A deleted story disappears at once (everything else skips it), and is removed for good, with its
recordings and voice files, once UNDO_SECONDS have passed. If the server stops in between, the
next start finishes the job.
"""

from __future__ import annotations

import logging
import threading

from ghostwriter import audio, db, tts
from ghostwriter.config import settings

log = logging.getLogger(__name__)

UNDO_SECONDS = 10


def delete(story_id: int) -> None:
    """Hide a story and the answers added to it; purge them when the Undo runs out."""
    db.set_deleted([story_id, *db.answer_ids(story_id)], True)
    _schedule_purge()


def _schedule_purge() -> None:
    timer = threading.Timer(UNDO_SECONDS + 1, purge)
    timer.daemon = True
    timer.start()


def restore(story_id: int) -> bool:
    """Undo a delete that hasn't been purged yet. False if it's too late."""
    story = db.get_story(story_id, include_deleted=True)
    if story is None:
        return False
    db.set_deleted([story_id, *db.answer_ids(story_id)], False)
    return True


def _files(story: dict) -> list:
    files = [settings.data_dir / p for p in (story["audio_original"], story["audio_wav"]) if p]
    if story["audio_original"]:
        files.append(audio.playback_copy(settings.data_dir / story["audio_original"]))
    return files + [path for text in (story["reaction"], story["retelling"]) if text for path in tts.cache_paths(text)]


def remove_now(story_id: int) -> None:
    """Delete a story and its answers for good: rows, search entries, recordings and voice files."""
    stories = [db.get_story(i, include_deleted=True) for i in [story_id, *db.answer_ids(story_id)]]
    db.delete_story(story_id)
    for story in filter(None, stories):
        for path in _files(story):
            path.unlink(missing_ok=True)


def purge(older_than: float = UNDO_SECONDS) -> int:
    """Remove every story whose Undo has run out. Returns how many."""
    ids = db.deleted_before(older_than)
    for story_id in ids:
        try:
            remove_now(story_id)
        except OSError:
            log.exception("could not remove the files of story %s", story_id)
    return len(ids)
