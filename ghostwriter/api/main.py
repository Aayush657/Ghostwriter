"""The FastAPI app: JSON API under /api, the memory book at /book, the web UI as static files at /.

Run:  .venv\\Scripts\\python.exe -m uvicorn ghostwriter.api.main:app --host 127.0.0.1 --port 8000
(127.0.0.1 means only this computer can open it; see README > Privacy before changing the host.)
"""

from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from ghostwriter import db, embed, export, llm, selfcheck, transcribe, trash, whispers
from ghostwriter.api import seance, stories, voice
from ghostwriter.config import settings
from ghostwriter.models import MOODS

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

log = logging.getLogger("ghostwriter")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s")
    db.init_db()
    if interrupted := db.mark_interrupted():
        log.warning("%d story(ies) were interrupted last time; they can be retried", interrupted)
    if purged := trash.purge(older_than=0):
        log.info("finished deleting %d story(ies) deleted before the last stop", purged)
    for check in selfcheck.run_checks():
        log.info("[%s] %s: %s", "ok" if check.ok else "!!", check.name, check.detail)
    threading.Thread(target=embed.refresh_quietly, daemon=True).start()  # stories saved before meaning search
    yield


app = FastAPI(title="Ghostwriter", lifespan=lifespan)
app.include_router(stories.router)
app.include_router(seance.router)
app.include_router(voice.router)


LOCAL_HOSTS = {"127.0.0.1", "localhost"}  # localhost too: people type it, and no website can claim it
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


@app.middleware("http")
async def only_this_page(request: Request, call_next):
    """Refuse other websites. A Host that isn't this computer means DNS rebinding; a state-changing
    request from another origin (or a cross-site Sec-Fetch-Site) means a page elsewhere is trying to
    change the archive. Requests without either header (curl, tests) carry no browser and may pass."""
    host = request.headers.get("host", "")
    if host.rsplit(":", 1)[0] not in LOCAL_HOSTS:
        return JSONResponse({"detail": "This archive only answers this computer."}, status_code=403)
    if request.method not in SAFE_METHODS:
        origin = request.headers.get("origin")
        fetch_site = request.headers.get("sec-fetch-site")
        if (origin is not None and origin != f"http://{host}") or \
                (origin is None and fetch_site not in (None, "same-origin", "none")):
            return JSONResponse({"detail": "Only this page can change the archive."}, status_code=403)
    return await call_next(request)


@app.middleware("http")
async def always_fresh_ui(request: Request, call_next):
    """Make browsers re-check UI files every time, so an updated page never shows stale code."""
    response = await call_next(request)
    if not request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.get("/api/health")
def health() -> list[dict]:
    """Which local services are available right now. The UI shows this in the About panel."""
    return [asdict(check) for check in selfcheck.run_checks()]


@app.post("/api/warm", status_code=204)
def warm() -> Response:
    """The page calls this when it opens and shows "waking the ghost" until it returns: Gemma, Whisper
    and the meaning-search model are loaded before the first story or question needs them."""
    whisper = threading.Thread(target=transcribe.warm_up, daemon=True)
    whisper.start()
    llm.warm_up()
    embed.refresh_quietly()
    whisper.join(timeout=60)
    return Response(status_code=204)


@app.get("/api/whisper")
def whisper() -> Response:
    """A line from an old, faded story, or 204 if the archive has nothing to whisper yet."""
    found = whispers.pick()
    return JSONResponse(found) if found else Response(status_code=204)


@app.get("/book", response_class=HTMLResponse)
def memory_book() -> str:
    """Every finished story as one self-contained, printable page (see export.py)."""
    return export.memory_book_html()


@app.get("/api/book", include_in_schema=False)
def old_book_address() -> RedirectResponse:
    return RedirectResponse("/book", status_code=308)


@app.delete("/api/samples")
def remove_samples() -> dict:
    """Remove the fictional sample stories in one go (they never mix with real ones, so nothing else changes)."""
    ids = [s["id"] for s in db.list_stories() if s["is_sample"] and s["status"] not in db.IN_PROGRESS]
    for story_id in ids:
        trash.remove_now(story_id)
    return {"removed": len(ids)}


@app.get("/api/settings")
def ui_settings() -> dict:
    """The defaults the page starts with (the visitor can still flip plain mode), and the shared lists."""
    return {"plain_mode_default": settings.plain_mode_default, "tts_enabled": settings.tts_enabled,
            "moods": list(MOODS), "undo_seconds": trash.UNDO_SECONDS,
            "max_recording_minutes": settings.max_audio_minutes}


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
