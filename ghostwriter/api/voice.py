"""The Archivist speaks: turn a piece of text into the ghost's voice (WAV), one part at a time.

The page asks for part 0, starts playing it, and fetches part 1 meanwhile (tts.parts says how text
is divided; the X-Parts header says how many there are).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ghostwriter import tts
from ghostwriter.tts import TTSError

router = APIRouter(prefix="/api", tags=["voice"])


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    plain: bool = False  # plain mode: the same voice without the ghost effects
    part: int = Field(0, ge=0)


@router.post("/speak")
def speak(req: SpeakRequest) -> FileResponse:
    parts = tts.parts(req.text)
    if req.part >= max(1, len(parts)):
        raise HTTPException(404, "There is no more to say.")
    try:
        path = tts.speak(parts[req.part] if parts else req.text, ghostly=not req.plain)
    except TTSError as exc:
        raise HTTPException(503, str(exc)) from None
    return FileResponse(path, media_type="audio/wav", headers={"X-Parts": str(len(parts))})
