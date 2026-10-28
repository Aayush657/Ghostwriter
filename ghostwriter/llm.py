"""Talking to Gemma through the local Ollama HTTP API. No cloud: Ollama runs the model on this machine."""

from __future__ import annotations

import logging

import httpx
from pydantic import ValidationError

from ghostwriter import prompts
from ghostwriter.config import settings
from ghostwriter.models import StoryAnalysis

log = logging.getLogger(__name__)

# CPU generation can take minutes, but a server that isn't running should fail fast.
TIMEOUT = httpx.Timeout(300, connect=5)


class LLMError(Exception):
    """Gemma couldn't be reached or gave no usable answer. The message is safe to show the user."""


def chat(messages: list[dict], *, schema: dict | None = None, temperature: float = 0.7) -> str:
    """One non-streaming chat call. `schema` forces the reply to follow a JSON schema."""
    body = {
        "model": settings.llm_model,
        "messages": messages,
        "stream": False,
        "think": False,  # Gemma 4 can reason before answering; we want direct, faster replies
        "options": {"temperature": temperature, "num_ctx": settings.llm_num_ctx},
    }
    if schema is not None:
        body["format"] = schema
    data = _post("/api/chat", body)
    if data.get("eval_duration"):
        log.info("gemma: %s prompt tokens, %s generated at %.1f tok/s", data.get("prompt_eval_count"),
                 data["eval_count"], data["eval_count"] / (data["eval_duration"] / 1e9))
    return data["message"]["content"]


def _post(path: str, body: dict) -> dict:
    try:
        resp = httpx.post(f"{settings.ollama_url}{path}", json=body, timeout=TIMEOUT)
    except httpx.ConnectError:
        raise LLMError("Ollama isn't running. Start it from the Start menu, or run: ollama serve") from None
    except httpx.TimeoutException:
        raise LLMError("Gemma took too long to answer. A smaller model may help "
                       "(set GW_LLM_MODEL=gemma4:e2b in .env).") from None
    if resp.status_code == 404:
        raise LLMError(f"The model {settings.llm_model} isn't downloaded. Run: ollama pull {settings.llm_model}")
    if resp.is_error:
        raise LLMError(f"Ollama returned an error: {resp.text[:300]}")
    return resp.json()


def analyse_story(transcript: str) -> StoryAnalysis:
    """Ask Gemma for a story's title, summary, entities and follow-up questions, as validated JSON.

    If the first reply doesn't validate, Gemma gets exactly one chance to repair it.
    """
    schema = StoryAnalysis.model_json_schema()
    messages = [
        {"role": "system", "content": prompts.ANALYSE_SYSTEM},
        {"role": "user", "content": prompts.analyse_user(transcript)},
    ]
    reply = chat(messages, schema=schema, temperature=0.2)
    try:
        return StoryAnalysis.model_validate_json(reply)
    except ValidationError as exc:
        log.warning("story JSON invalid, asking Gemma to repair it: %s", exc)
        messages += [{"role": "assistant", "content": reply},
                     {"role": "user", "content": prompts.repair(str(exc))}]
    reply = chat(messages, schema=schema, temperature=0)
    try:
        return StoryAnalysis.model_validate_json(reply)
    except ValidationError as exc:
        raise LLMError("The Archivist couldn't make sense of this story. Try again.") from exc
