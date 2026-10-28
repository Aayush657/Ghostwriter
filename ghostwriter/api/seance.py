"""Seance: ask the archive a question. The Archivist answers only from your stories, streamed live.

Events, in order:  sources {stories: [{id, title}]}  ->  token {text} ...  ->  done {cited: [ids]}
                   (or error {message} if Gemma can't be reached)
"""

from __future__ import annotations

import re
from collections.abc import Iterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ghostwriter import llm, prompts, search
from ghostwriter.api.sse import sse, stream
from ghostwriter.llm import LLMError

router = APIRouter(prefix="/api", tags=["seance"])


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    plain: bool = False


@router.post("/seance")
def seance(q: Question) -> StreamingResponse:
    return stream(_answer(q))


def _answer(q: Question) -> Iterator[str]:
    stories = search.find_stories(q.question)
    yield sse("sources", {"stories": [{"id": s["id"], "title": s["title"]} for s in stories]})

    if not stories:
        # Nothing matched, so Gemma is not even asked: there is nothing it could honestly say.
        known = bool(search.keywords(q.question))
        yield sse("token", {"text": prompts.UNKNOWN[q.plain] if known else prompts.NO_KEYWORDS[q.plain]})
        yield sse("done", {"cited": []})
        return

    answer = []
    try:
        for piece in llm.stream_chat(prompts.seance_messages(q.question, stories, q.plain), temperature=0.3):
            answer.append(piece)
            yield sse("token", {"text": piece})
    except LLMError as exc:
        yield sse("error", {"message": str(exc)})
        return

    # Only citations of stories Gemma was actually shown become links.
    cited = {int(n) for n in re.findall(r"\[S(\d+)\]", "".join(answer))}
    yield sse("done", {"cited": sorted(cited & {s["id"] for s in stories})})
