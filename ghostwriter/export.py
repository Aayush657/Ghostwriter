"""The memory book: every finished story in one self-contained, printable HTML file.

Answers to the Archivist's questions appear inside the story they complete, under the question.

Open it in any browser, print it to PDF, or keep the file itself. The fonts are embedded, so it
needs no server, no internet and no Ghostwriter to be read, now or in twenty years.
(Recordings aren't included; they stay in data/audio/.)
"""

from __future__ import annotations

import base64
import sys
from datetime import datetime, timezone
from html import escape
from pathlib import Path

from ghostwriter import db
from ghostwriter.config import PROJECT_ROOT

FONTS = PROJECT_ROOT / "ghostwriter" / "static" / "fonts"
PUBLIC_DIR = PROJECT_ROOT / "docs"  # the project website: whatever is written here gets published
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
a { color: #7a3d0c; text-decoration-color: #d9a066; text-underline-offset: 3px; }
a:hover, a:focus-visible { color: #b4520a; }
ol li { margin: 4px 0; }
.added { margin: 6px 0 14px 18px; padding-left: 12px; border-left: 3px solid #d9a066; }
.added .meta { margin: 0; }
.print {
  font: inherit; margin-top: 18px; padding: 8px 22px; cursor: pointer; border: 0; border-radius: 999px;
  background: #7a3d0c; color: #fff8ec; box-shadow: 0 2px 10px rgba(122, 61, 12, 0.3);
}
.print:hover, .print:focus-visible { background: #b4520a; outline: 2px solid #b4520a; outline-offset: 2px; }
@page { margin: 18mm 16mm; }
@media print {
  .print { display: none; }
  body { background: none; font-size: 12pt; }
  main { padding: 0; max-width: none; }
  a { color: inherit; text-decoration: none; }
  .cover { padding-top: 30vh; }
  .story { break-before: page; border: 0; margin: 0; }
  h2, h3 { break-after: avoid; }
  p, li { orphans: 3; widows: 3; }
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
    questions = "".join(f"<li>{escape(q['text'])}{_answer(q['answer'])}</li>" for q in s["questions"])
    parts = [
        f'<section class="story" id="s{s["id"]}">',
        f"<h2>{escape(s['title'])}</h2>",
        f'<p class="meta">{escape(meta)}</p>',
        f"<p>{escape(s['summary'])}</p>",
        '<p class="meta">Some words were unclear, so the summary leaves them out.</p>' if s["uncertain"] else "",
        f"<dl>{rows}</dl>" if rows else "",
        f'<h3>The words as they were spoken</h3><p class="transcript">{escape(s["transcript"])}</p>',
        f'<h3>The Archivist wrote</h3><p class="hand">{escape(s["reaction"])}</p>' if s["reaction"] else "",
        f"<h3>Unfinished business</h3><ul>{questions}</ul>" if questions else "",
        ('<h3>A haunted retelling</h3><p class="meta">A retelling by the Archivist, not the memory itself.</p>'
         f'<p class="hand">{escape(s["retelling"])}</p>') if s["retelling"] else "",
        "</section>",
    ]
    return "\n".join(p for p in parts if p)


def _answer(answer: dict | None) -> str:
    """An answer recorded later, shown under its question."""
    if not answer or answer["status"] != "ready":
        return ""
    return (f'<div class="added"><p class="meta">Added later, {_local_date(answer["created_at"])}</p>'
            f'<p>{escape(answer["summary"] or "")}</p>'
            f'<p class="transcript">{escape(answer["transcript"] or "")}</p></div>')


def memory_book_html() -> str:
    """The whole archive, oldest story first, as one HTML page with nothing to fetch."""
    stories = [db.get_story(s["id"]) for s in reversed(db.list_stories())
               if s["status"] == "ready" and not s["parent_id"]]
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
<p class="hand">{len(stories)} {"memory" if len(stories) == 1 else "memories"}, kept by the ghost on this computer.</p>
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


def save(out: Path) -> None:
    """Write the memory book to a file. Only an archive of fictional samples may go into docs/."""
    if out.resolve().is_relative_to(PUBLIC_DIR) and not all(s["is_sample"] for s in db.list_stories()):
        raise ValueError("docs/ is the public website and this archive holds real stories. "
                         'Export the samples instead: $env:GW_DATA_DIR = "demo-data"')
    out.write_text(memory_book_html(), encoding="utf-8")


if __name__ == "__main__":
    # .venv\Scripts\python.exe -m ghostwriter.export memory-book.html
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "memory-book.html")
    try:
        save(target)
    except ValueError as e:
        sys.exit(str(e))
    print(f"Wrote {target}")
