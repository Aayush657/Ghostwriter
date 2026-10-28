"""Server-Sent Events: how Gemma's words travel to the page one piece at a time."""

from __future__ import annotations

import json
from collections.abc import Iterator

from fastapi.responses import StreamingResponse


def sse(event: str, data: dict) -> str:
    """One event. The data is JSON, so newlines inside the text can't break the stream format."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def stream(events: Iterator[str]) -> StreamingResponse:
    return StreamingResponse(events, media_type="text/event-stream", headers={"Cache-Control": "no-cache"})
