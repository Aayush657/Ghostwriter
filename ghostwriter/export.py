"""The memory book: every finished story in one self-contained, printable HTML file.

Open it in any browser, print it to PDF, or keep the file itself. The fonts are embedded, so it
needs no server, no internet and no Ghostwriter to be read, now or in twenty years.
(Recordings aren't included; they stay in data/audio/.)
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from html import escape

from ghostwriter import db
from ghostwriter.config import PROJECT_ROOT

FONTS = PROJECT_ROOT / "ghostwriter" / "static" / "fonts"
ENTITY_LABELS = (("person", "People"), ("place", "Places"), ("era", "When"), ("keepsake", "Keepsakes"))

STYLE = """
body { margin: 0; background: #f4ecd9; color: #2b241c; font: 17px/1.65 Georgia, "Nirmala UI", serif; }
main { max-width: 720px; margin: 0 auto; padding: 40px 24px; }
h1, h2, h3 { font-family: "IM Fell English", Georgia, serif; font-weight: normal; color: #7a3d0c; }
h1 { font-size: 2.6rem; margin: 0; }
h3 { font-size: 1.1rem; margin: 24px 0 4px; }
.meta { color: #7b6d5a; font-size: 0.9rem; }
.hand { font-family: "Caveat", cursive; font-size: 1.45rem; line-height: 1.35; white-space: pre-wrap; }
.transcript { white-space: pre-wrap; }
dl { display: grid; grid-template-columns: max-content 1fr; gap: 2px 16px; }
dt { color: #7b6d5a; }
dd { margin: 0; }
.story { border-top: 1px solid #d6c7a6; margin-top: 40px; padding-top: 8px; }
.cover { text-align: center; padding: 80px 0 40px; }
.print { font: inherit; margin-top: 16px; padding: 6px 16px; cursor: pointer; }
@media print {
  .print { display: none; }
  body { background: none; }
  .story { break-before: page; border: 0; margin: 0; }
}
"""


def _font_face(family: str, filename: str) -> str:
    data = base64.b64encode((FONTS / filename).read_bytes()).decode("ascii")
    return f'@font-face {{ font-family: "{family}"; src: url(data:font/ttf;base64,{data}) format("truetype"); }}'


def _local_date(utc: str) -> str:
    """'2026-10-28 10:47:38' (UTC, as SQLite stores it) -> '28 October 2026' in this computer's time zone."""
    moment = datetime.fromisoformat(utc).replace(tzinfo=timezone.utc).astimezone()
    return f"{moment.day} {moment:%B %Y}"


def _story(s: dict) -> str:
    entities = s["entities"]
    rows = "".join(f"<dt>{label}</dt><dd>{escape(', '.join(entities[kind]))}</dd>"
                   for kind, label in ENTITY_LABELS if entities.get(kind))
    meta = " · ".join(filter(None, [_local_date(s["created_at"]), s["mood"],
                                    "fictional sample" if s["is_sample"] else ""]))
    questions = "".join(f"<li>{escape(q['text'])}{' <em>(answered)</em>' if q['answered_by'] else ''}</li>"
                        for q in s["questions"])
    parts = [
        f'<section class="story" id="s{s["id"]}">',
        f"<h2>{escape(s['title'])}</h2>",
        f'<p class="meta">{escape(meta)}</p>',
        f"<p>{escape(s['summary'])}</p>",
        f"<dl>{rows}</dl>" if rows else "",
        f'<h3>The words as they were spoken</h3><p class="transcript">{escape(s["transcript"])}</p>',
        f'<h3>The Archivist wrote</h3><p class="hand">{escape(s["reaction"])}</p>' if s["reaction"] else "",
        f"<h3>Unfinished business</h3><ul>{questions}</ul>" if questions else "",
        ('<h3>A haunted retelling</h3><p class="meta">A retelling by the Archivist, not the memory itself.</p>'
         f'<p class="hand">{escape(s["retelling"])}</p>') if s["retelling"] else "",
        "</section>",
    ]
    return "\n".join(p for p in parts if p)


def memory_book_html() -> str:
    """The whole archive, oldest story first, as one HTML page with nothing to fetch."""
    stories = [db.get_story(s["id"]) for s in reversed(db.list_stories()) if s["status"] == "ready"]
    today = _local_date(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))
    contents = "".join(f'<li><a href="#s{s["id"]}">{escape(s["title"])}</a></li>' for s in stories)
    fonts = _font_face("Caveat", "Caveat.ttf") + _font_face("IM Fell English", "IMFellEnglish-Regular.ttf")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ghostwriter memory book, {today}</title>
<style>{fonts}{STYLE}</style>
</head>
<body>
<main>
<div class="cover">
<h1>The Memory Book</h1>
<p class="hand">{len(stories)} {"memory" if len(stories) == 1 else "memories"}, kept by the ghost in this laptop.</p>
<p class="meta">Written down by Ghostwriter on {today}.</p>
<button class="print" onclick="print()">Print, or save as PDF</button>
</div>
<h3>Contents</h3>
<ol>{contents}</ol>
{"".join(_story(s) for s in stories)}
</main>
</body>
</html>
"""
