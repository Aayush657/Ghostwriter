"""Load the fictional sample stories (samples/stories.json) into a demo archive.

Samples never go into your real archive. Run them in their own data folder:
    $env:GW_DATA_DIR = "demo-data"; .venv\\Scripts\\python.exe -m ghostwriter.samples
Gemma analyses each sample exactly as it would a real recording (minus the audio steps).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone

from ghostwriter import db, pipeline
from ghostwriter.config import PROJECT_ROOT, settings

SAMPLES_FILE = PROJECT_ROOT / "samples" / "stories.json"
REAL_DATA_DIR = PROJECT_ROOT / "data"


def seed() -> list[int]:
    """Add every sample story and analyse it. Does nothing if samples are already present."""
    db.init_db()
    if any(s["is_sample"] for s in db.list_stories()):
        print("The samples are already in this archive.")
        return []
    ids = []
    for sample in json.loads(SAMPLES_FILE.read_text(encoding="utf-8"))["stories"]:
        story_id = db.create_story(is_sample=True)
        db.update_story(story_id, transcript=sample["transcript"], language=sample["language"])
        pipeline.process_story(story_id)
        # Pretend some samples were last opened weeks ago, so the candle wall shows fading.
        visited = datetime.now(timezone.utc) - timedelta(days=sample.get("days_unvisited", 0))
        db.update_story(story_id, last_visited_at=visited.strftime("%Y-%m-%d %H:%M:%S"))
        story = db.get_story(story_id)
        print(f"  [{story['status']}] {sample['key']}: {story['title'] or story['error']}")
        ids.append(story_id)
    return ids


if __name__ == "__main__":
    if settings.data_dir.resolve() == REAL_DATA_DIR.resolve():
        sys.exit('Refusing to mix samples into your real archive. First run: $env:GW_DATA_DIR = "demo-data"')
    print(f"Adding fictional sample stories to {settings.data_dir} (Gemma analyses each; about a minute each)")
    seed()
