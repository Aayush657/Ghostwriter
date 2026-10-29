"""Talking to Gemma through the local Ollama HTTP API. No cloud: Ollama runs the model on this machine."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager

import httpx
from pydantic import ValidationError

from ghostwriter import prompts, tags
from ghostwriter.config import settings
from ghostwriter.models import StoryAnalysis

log = logging.getLogger(__name__)

# CPU generation can take minutes, but a server that isn't running should fail fast.
TIMEOUT = httpx.Timeout(300, connect=5)
# Keep Gemma in memory between questions (Ollama's default is 5 minutes); loading it takes ~16-20 s.
KEEP_ALIVE = "20m"


class LLMError(Exception):
    """Gemma couldn't be reached or gave no usable answer. The message is safe to show the user."""


def _body(messages: list[dict], *, stream: bool, temperature: float, schema: dict | None = None) -> dict:
    body = {
        "model": settings.llm_model,
        "messages": messages,
        "stream": stream,
        "think": False,  # Gemma 4 can reason before answering; we want direct, faster replies
        "keep_alive": KEEP_ALIVE,
        "options": {"temperature": temperature, "num_ctx": settings.llm_num_ctx},
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


def analyse_story(transcript: str, answering: str | None = None) -> StoryAnalysis:
    """Ask Gemma for a story's title, summary, entities and follow-up questions, as validated JSON.

    If the first reply doesn't validate, Gemma gets exactly one chance to repair it.
    """
    schema = StoryAnalysis.model_json_schema()
    messages = [
        {"role": "system", "content": prompts.ANALYSE_SYSTEM},
        {"role": "user", "content": prompts.analyse_user(transcript, answering)},
    ]
    reply = chat(messages, schema=schema, temperature=0.2)
    try:
        return tags.clean(StoryAnalysis.model_validate_json(reply))
    except ValidationError as exc:
        log.warning("story JSON invalid, asking Gemma to repair it: %s", exc)
        messages += [{"role": "assistant", "content": reply},
                     {"role": "user", "content": prompts.repair(str(exc))}]
    reply = chat(messages, schema=schema, temperature=0)
    try:
        return tags.clean(StoryAnalysis.model_validate_json(reply))
    except ValidationError as exc:
        raise LLMError("The Archivist couldn't make sense of this story. Try again.") from exc


ANSWERED_SCHEMA = {"type": "object", "properties": {"answered": {"type": "array", "items": {"type": "boolean"}}},
                   "required": ["answered"]}


def unanswered_questions(transcript: str, analysis: StoryAnalysis, answering: str | None = None) -> list[str]:
    """Drop follow-up questions the transcript already answers ("What kind of car?" when it says "a Fiat").

    Gemma checks its own questions in the same conversation, so Ollama reuses the transcript it has
    already read and the check costs a few seconds. If the check fails, every question is kept.
    """
    questions = analysis.unfinished_business
    messages = [
        {"role": "system", "content": prompts.ANALYSE_SYSTEM},
        {"role": "user", "content": prompts.analyse_user(transcript, answering)},
        {"role": "assistant", "content": analysis.model_dump_json()},
        {"role": "user", "content": prompts.CHECK_QUESTIONS},
    ]
    try:
        answered = json.loads(chat(messages, schema=ANSWERED_SCHEMA, temperature=0))["answered"]
    except (LLMError, ValueError, KeyError, TypeError) as exc:
        log.warning("question check skipped: %s", exc)
        return questions
    if len(answered) != len(questions):
        return questions
    kept = [q for q, done in zip(questions, answered) if not done]
    if len(kept) < len(questions):
        log.info("dropped questions the transcript already answers: %s",
                 [q for q, done in zip(questions, answered) if done])
    return kept


def write_note(story: dict) -> str:
    """The Archivist's note about a story, written once while the story is processed."""
    return chat(prompts.reaction_messages(story), temperature=0.8).strip()
