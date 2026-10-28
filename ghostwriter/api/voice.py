"""The Archivist speaks: turn a piece of text into the ghost's voice (WAV)."""

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


@router.post("/speak")
def speak(req: SpeakRequest) -> FileResponse:
    try:
        path = tts.speak(req.text, ghostly=not req.plain)
    except TTSError as exc:
        raise HTTPException(503, str(exc)) from None
    return FileResponse(path, media_type="audio/wav")
