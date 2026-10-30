"""Server-Sent Events: how Gemma's words travel to the page one piece at a time."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterator

from fastapi import Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse


def sse(event: str, data: dict) -> str:
    """One event. The data is JSON, so newlines inside the text can't break the stream format."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def until_gone(request: Request | None, events: Iterator[str]) -> AsyncIterator[str]:
    """Pass the events on while the page listens. When it goes away (Stop, a new question, a closed
    tab) the generator is closed, which closes Ollama's stream, and Ollama stops writing."""
    try:
        while (item := await run_in_threadpool(next, events, None)) is not None:
            if request is not None and await request.is_disconnected():
                break
            yield item
    finally:
        events.close()


def stream(events: Iterator[str], request: Request | None = None) -> StreamingResponse:
    return StreamingResponse(until_gone(request, events), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache"})
