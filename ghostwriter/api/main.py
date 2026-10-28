"""The FastAPI app: JSON API under /api, the web UI as static files at /.

Run:  .venv\\Scripts\\python.exe -m uvicorn ghostwriter.api.main:app --port 8000
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from ghostwriter import db, selfcheck, whispers
from ghostwriter.api import seance, stories
from ghostwriter.config import settings

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

log = logging.getLogger("ghostwriter")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s")
    db.init_db()
    if interrupted := db.mark_interrupted():
        log.warning("%d story(ies) were interrupted last time; they can be retried", interrupted)
    for check in selfcheck.run_checks():
        log.info("[%s] %s: %s", "ok" if check.ok else "!!", check.name, check.detail)
    yield


app = FastAPI(title="Ghostwriter", lifespan=lifespan)
app.include_router(stories.router)
app.include_router(seance.router)


@app.middleware("http")
async def always_fresh_ui(request: Request, call_next):
    """Make browsers re-check UI files every time, so an updated page never shows stale code."""
    response = await call_next(request)
    if not request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.get("/api/health")
def health() -> list[dict]:
    """Which local services are available right now. The UI shows this."""
    return [asdict(check) for check in selfcheck.run_checks()]


@app.get("/api/whisper")
def whisper() -> Response:
    """A line from an old, faded story, or 204 if the archive has nothing to whisper yet."""
    found = whispers.pick()
    return JSONResponse(found) if found else Response(status_code=204)


@app.get("/api/settings")
def ui_settings() -> dict:
    """The defaults the page starts with (the visitor can still flip plain mode)."""
    return {"plain_mode_default": settings.plain_mode_default, "tts_enabled": settings.tts_enabled}


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
