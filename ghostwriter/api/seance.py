"""Seance: ask the archive a question. The Archivist answers only from your stories, streamed live.

Events, in order:  sources {stories: [{id, title}]}  ->  token {text} and cite {id} ...  ->  done {cited: [ids]}
                   (or error {message} if Gemma can't be reached)

Gemma writes citations as [S3]. They are taken out of the text here, even when one arrives split
across pieces ("[S", "3]"), and sent as cite events, so the page never shows a raw marker.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ghostwriter import llm, prompts, search
from ghostwriter.api.sse import sse, stream
from ghostwriter.llm import LLMError

router = APIRouter(prefix="/api", tags=["seance"])

CITATION = re.compile(r"\s*\[S(\d+(?:\s*,\s*S?\d+)*)\]")  # [S3], also [S3, S5]
# The end of the text so far might still become a citation: hold it back until the next piece.
UNFINISHED = re.compile(r"\s*(\[(S[\d,\sS]*)?)?$")


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    plain: bool = False


@router.post("/seance")
def seance(q: Question, request: Request) -> StreamingResponse:
    return stream(_answer(q), request)


def split_citations(pieces: Iterable[str]) -> Iterator[tuple[str, str | int]]:
    """("text", "...") and ("cite", 3) in reading order, from Gemma's streamed pieces."""
    held = ""
    for piece in pieces:
        held += piece
        cut = UNFINISHED.search(held).start()
        yield from _parts(held[:cut])
        held = held[cut:]
    yield from _parts(held)


def _parts(text: str) -> Iterator[tuple[str, str | int]]:
    pos = 0
    for match in CITATION.finditer(text):
        if match.start() > pos:
            yield "text", text[pos:match.start()]
        for number in re.findall(r"\d+", match.group(1)):
            yield "cite", int(number)
        pos = match.end()
    if pos < len(text):
        yield "text", text[pos:]


def _answer(q: Question) -> Iterator[str]:
    stories = search.find_stories(q.question)
    yield sse("sources", {"stories": [{"id": s["id"], "title": s["title"]} for s in stories]})

    if not stories:
        # Nothing matched, so Gemma is not even asked: there is nothing it could honestly say.
        known = bool(search.keywords(q.question))
        yield sse("token", {"text": prompts.UNKNOWN[q.plain] if known else prompts.NO_KEYWORDS[q.plain]})
        yield sse("done", {"cited": []})
        return

    shown = {s["id"] for s in stories}
    cited = []
    try:
        pieces = llm.stream_chat(prompts.seance_messages(q.question, stories, q.plain), temperature=0.3)
        for kind, value in split_citations(pieces):
            if kind == "text":
                yield sse("token", {"text": value})
            elif value in shown:  # only stories Gemma was actually shown become links
                cited.append(value)
                yield sse("cite", {"id": value})
    except LLMError as exc:
        yield sse("error", {"message": str(exc)})
        return
    yield sse("done", {"cited": sorted(set(cited))})
