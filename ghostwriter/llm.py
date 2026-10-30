"""Talking to Gemma through the local Ollama HTTP API. No cloud: Ollama runs the model on this machine."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterator
from contextlib import contextmanager

import httpx
from pydantic import ValidationError

from ghostwriter import prompts, tags
from ghostwriter.config import settings
from ghostwriter.models import META_TEXT, StoryAnalysis
from ghostwriter.whispers import SENTENCE_END

log = logging.getLogger(__name__)

# CPU generation can take minutes, but a server that isn't running should fail fast.
TIMEOUT = httpx.Timeout(300, connect=5)
# Keep Gemma in memory between questions (Ollama's default is 5 minutes); loading it takes ~16-20 s.
KEEP_ALIVE = "20m"


class LLMError(Exception):
    """Gemma couldn't be reached or gave no usable answer. The message is safe to show the user."""


class UnclearStory(Exception):
    """Gemma could only describe the words themselves ("the transcript is garbled"), not a memory."""


SEED = 7  # with temperature 0, re-reading the same words gives the same title, mood and tags


def _body(messages: list[dict], *, stream: bool, temperature: float, schema: dict | None = None) -> dict:
    body = {
        "model": settings.llm_model,
        "messages": messages,
        "stream": stream,
        "think": False,  # Gemma 4 can reason before answering; we want direct, faster replies
        "keep_alive": KEEP_ALIVE,
        "options": {"temperature": temperature, "num_ctx": settings.llm_num_ctx, "seed": SEED},
    }
    if schema is not None:
        body["format"] = schema
    return body


def warm_up() -> None:
    """Load Gemma ahead of the first question (an empty chat only loads the model). Never raises."""
    try:
        httpx.post(f"{settings.ollama_url}/api/chat", timeout=TIMEOUT, json={
            "model": settings.llm_model, "messages": [], "keep_alive": KEEP_ALIVE,
            "options": {"num_ctx": settings.llm_num_ctx},  # same context size, or Ollama loads it twice
        })
    except httpx.HTTPError as exc:
        log.info("could not warm up Gemma: %s", exc)  # the health banner already explains why


@contextmanager
def _friendly_errors() -> Iterator[None]:
    """Turn network failures into messages a person can act on."""
    try:
        yield
    except httpx.ConnectError:
        raise LLMError("Ollama isn't running. Start it from the Start menu, or run: ollama serve") from None
    except httpx.TimeoutException:
        raise LLMError("Gemma took too long to answer. A smaller model may help "
                       "(set GW_LLM_MODEL=gemma4:e2b in .env).") from None


def _ollama_error(detail: str) -> LLMError:
    if "allocate" in detail:  # Ollama couldn't find enough free RAM to load the model
        return LLMError("Gemma couldn't fit in memory right now. Close some programs (browser tabs, games) and "
                        "try again, or use the smaller model: set GW_LLM_MODEL=gemma4:e2b in .env.")
    return LLMError(f"Ollama returned an error: {detail[:300]}")


def _check(resp: httpx.Response) -> None:
    if resp.status_code == 404:
        raise LLMError(f"The model {settings.llm_model} isn't downloaded. Run: ollama pull {settings.llm_model}")
    if resp.is_error:
        raise _ollama_error(resp.read().decode(errors="replace"))


def _log_speed(data: dict) -> None:
    if data.get("eval_duration"):
        log.info("gemma: %s prompt tokens, %s generated at %.1f tok/s", data.get("prompt_eval_count"),
                 data["eval_count"], data["eval_count"] / (data["eval_duration"] / 1e9))


def chat(messages: list[dict], *, schema: dict | None = None, temperature: float = 0.7) -> str:
    """One non-streaming chat call. `schema` forces the reply to follow a JSON schema."""
    with _friendly_errors():
        resp = httpx.post(f"{settings.ollama_url}/api/chat", timeout=TIMEOUT,
                          json=_body(messages, stream=False, temperature=temperature, schema=schema))
    _check(resp)
    data = resp.json()
    _log_speed(data)
    return data["message"]["content"]


def stream_chat(messages: list[dict], *, temperature: float = 0.7) -> Iterator[str]:
    """Yield Gemma's reply piece by piece as it is generated (for the ghost-handwriting effect)."""
    with _friendly_errors(), httpx.stream(
        "POST", f"{settings.ollama_url}/api/chat", timeout=TIMEOUT,
        json=_body(messages, stream=True, temperature=temperature),
    ) as resp:
        _check(resp)
        for line in resp.iter_lines():
            if not line:
                continue
            chunk = json.loads(line)
            if "error" in chunk:
                raise _ollama_error(chunk["error"])
            if piece := chunk.get("message", {}).get("content"):
                yield piece
            if chunk.get("done"):
                _log_speed(chunk)


def _messages(transcript: str, answering: dict | None, written: bool = False) -> list[dict]:
    return [
        {"role": "system", "content": prompts.analyse_system(answering)},
        {"role": "user", "content": prompts.analyse_user(transcript, answering, written)},
    ]


def _validated(reply: str, answering: dict | None) -> StoryAnalysis:
    analysis = tags.clean(StoryAnalysis.model_validate_json(reply))
    if answering:  # an answer completes an earlier memory; it opens no new questions
        analysis.unfinished_business = []
    return analysis


def analyse_story(transcript: str, answering: dict | None = None, written: bool = False) -> StoryAnalysis:
    """Ask Gemma for a story's title, summary, entities and follow-up questions, as validated JSON.

    `answering` is the question this recording answers, with its story (db.get_story()["answers"]).
    If the first reply doesn't validate, Gemma gets exactly one chance to repair it. If it still talks
    about "the transcript" instead of a memory, the words were too unclear: UnclearStory.
    """
    schema = StoryAnalysis.model_json_schema()
    messages = _messages(transcript, answering, written)
    reply = chat(messages, schema=schema, temperature=0)
    try:
        return _validated(reply, answering)
    except ValidationError as exc:
        log.warning("story JSON invalid, asking Gemma to repair it: %s", exc)
        messages += [{"role": "assistant", "content": reply},
                     {"role": "user", "content": prompts.repair(str(exc))}]
    reply = chat(messages, schema=schema, temperature=0)
    try:
        return _validated(reply, answering)
    except ValidationError as exc:
        if META_TEXT.search(reply):
            raise UnclearStory() from exc
        raise LLMError("Gemma couldn't make sense of this story. Try again.") from exc


CHECK_SCHEMA = {"type": "object", "properties": {"checks": {"type": "array", "items": {
    "type": "object", "properties": {"about": {"type": "string", "maxLength": 80}, "answered": {"type": "boolean"},
                                     "unknown": {"type": "boolean"}},
    "required": ["about", "answered", "unknown"]}}}, "required": ["checks"]}

# Ways a storyteller says nobody knows (English, Hindi, Hinglish).
NOT_KNOWN = re.compile(
    r"never (found|knew|learn|told|discover|saw|figured|heard|came to know)|(do|did|does)n'?t know|not know|"
    r"nobody (knows|ever)|no one (knows|ever)|still wonder|a mystery|नहीं पता|पता नहीं|मालूम नहीं|नहीं मालूम|"
    r"कोई नहीं जानता|nahi+n? pata|pata nahi+n?|malum nahi", re.IGNORECASE)


def says_unknown(transcript: str, about: str) -> bool:
    """Does the sentence `about` points to really say nobody knows? Gemma judges "unknown" too broadly
    on its own (it called "What did the almirah look like?" unknown because the lock was never found)."""
    words = set(about.lower().split())
    if not words:
        return False
    sentence = max(SENTENCE_END.split(transcript), key=lambda s: len(words & set(s.lower().split())))
    return bool(NOT_KNOWN.search(sentence))


def unanswered_questions(transcript: str, analysis: StoryAnalysis, answering: dict | None = None) -> list[str]:
    """Drop follow-up questions the story already answers ("What kind of car?" when it says "a Fiat"),
    or that it says nobody can answer ("Who made the tea?" when "grandmother never told me who made it").

    Gemma checks its own questions in the same conversation, so Ollama reuses the words it has already
    read, and names the words each question is about; "nobody knows" counts only when those words'
    sentence says so. If the check fails, every question is kept.
    """
    questions = analysis.unfinished_business
    if not questions:
        return questions
    messages = [
        *_messages(transcript, answering),
        {"role": "assistant", "content": analysis.model_dump_json()},
        {"role": "user", "content": prompts.CHECK_QUESTIONS},
    ]
    try:
        checks = json.loads(chat(messages, schema=CHECK_SCHEMA, temperature=0))["checks"]
        drop = [c["answered"] or (c["unknown"] and says_unknown(transcript, c["about"])) for c in checks]
    except (LLMError, ValueError, KeyError, TypeError) as exc:
        log.warning("question check skipped: %s", exc)
        return questions
    if len(drop) != len(questions):
        return questions
    kept = [q for q, dropped in zip(questions, drop) if not dropped]
    if len(kept) < len(questions):
        log.info("dropped questions the story already answers or can't: %s",
                 [q for q, dropped in zip(questions, drop) if dropped])
    return kept


def write_note(story: dict) -> str:
    """The Archivist's note about a story, written once while the story is processed."""
    return chat(prompts.reaction_messages(story), temperature=0.8).strip()
