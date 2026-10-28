# Ghostwriter: build plan

Hacktoberfest Open-Source AI Challenge, Week 4: "Ghost in the Machine".
Deadline: **Sun Nov 1, 2026, 12:29 PM IST** (Oct 31, 11:59 PM PDT).
Feature freeze: **Sat Oct 31, 10:00 PM IST**.

## Architecture

```
 Browser (plain HTML/CSS/JS, all assets bundled, no CDN)
   |  record (MediaRecorder) / upload            ^  SSE token stream ("ghost handwriting")
   v                                             |
 FastAPI (uvicorn, 127.0.0.1 only)  -------------+
   |
   +-- audio.py       ffmpeg -> 16 kHz mono wav (original kept for playback)
   +-- transcribe.py  faster-whisper (CPU int8, language auto-detect: hi / en / mixed)
   +-- llm.py         Ollama /api/chat (Gemma 4), JSON-schema output, validate, 1 repair retry
   +-- prompts.py     every prompt + the Archivist persona, in one place
   +-- db.py          SQLite: stories, entities, follow-ups; FTS5 index over transcripts
   +-- search.py      FTS5 retrieval for Seance (grounded answers with citations)
   +-- tts.py         Piper (subprocess) + ffmpeg reverb/pitch, optional
   +-- selfcheck.py   which local services are up (Ollama, model, Whisper, ffmpeg, TTS)

 Everything lives on this laptop:
   data/ghostwriter.db, data/audio/   (private, git-ignored)
   models/whisper/                    (faster-whisper weights)
   C:\Users\aayus\Tools\              (ffmpeg, Ollama, Ollama models, Piper)
```

Processing is after-the-fact, not live: a recording finishes, then a background
job transcribes it, asks Gemma for the structured JSON, and stores it. The UI
polls the job state.

## File tree (target)

```
ghostwriter/
  ghostwriter/            Python package
    config.py             settings from .env (model names, paths, feature flags)
    selfcheck.py          environment / service checks (CLI + used at startup)
    audio.py  transcribe.py  llm.py  prompts.py  db.py  search.py  tts.py
    api/                  FastAPI routers (stories, seance, health, tts)
    static/               index.html, css, js, fonts, sounds (all local)
  samples/                3-4 clearly fictional demo stories (kept apart from real data)
  scripts/setup.ps1       one-command Windows setup
  tests/                  pytest, LLM and Whisper mocked
  README.md  PROGRESS.md  PLAN.md  HOW_IT_WORKS.md  POST_DRAFT.md  DEMO_SCRIPT.md  LICENSE
```

## Model choices (CPU-only laptop: i7-13620H, 16 GB RAM, no NVIDIA GPU)

- **LLM:** `gemma4:e4b` (Gemma 4 "effective 4B", the default Ollama tag). The
  12B/26B/31B models are too slow without a GPU. If e4b is under ~6 tokens/s,
  switch to `gemma4:e2b` (one line in `.env`). Thinking mode is turned off
  (`think: false`) because we want fast, direct answers.
- **Speech-to-text:** faster-whisper `small`, int8 on CPU. `medium` will be
  benchmarked on a real Hindi/Hinglish clip, and the winner goes in `.env`.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Gemma is slow on CPU | Measure first; e2b fallback; short prompts; stream so it *feels* alive |
| Gemma returns bad JSON | Ollama JSON-schema `format`, pydantic validation, one repair retry, then store a "raw" story rather than lose it |
| Hindi / code-mixed transcription quality | Auto-detect language; let the user pick `medium`; test with a real clip |
| FTS5 and Devanagari tokenising | SQLite 3.38 has the `trigram` tokenizer (script-agnostic); test both |
| 16 GB RAM with Whisper + Gemma loaded | Run jobs one at a time; Whisper loads lazily |
| Piper on Windows | It's P1 and optional: run it as a subprocess, fail gracefully to text-only |
| Running out of time | Every stage ends in a committed, working app; cut from the bottom of the priority list, and ask before cutting any P0/P1 |

## Timeline (IST)

| When | Stage | Done when |
|---|---|---|
| Wed Oct 28, afternoon | 0: setup | git, docs, venv, self-check green, Gemma replies |
| Wed Oct 28 evening to Thu Oct 29 midday | 1: core pipeline | a real recording becomes a stored, tagged story |
| Thu Oct 29 afternoon to night | 2: Seance, Archivist, handwriting stream, Unfinished Business | grounded Q&A with citations, streamed |
| Fri Oct 30 | 3: candle wall, whispers, browser recording, polish | demo-able UI |
| Fri Oct 30 night | 4: ghost voice (Piper + ffmpeg) | the Archivist speaks, or degrades cleanly |
| Sat Oct 31, day | 5: retelling, export, .tech landing page | stretch, cut if late |
| Sat Oct 31, before 10 PM | 6: README, HOW_IT_WORKS, DEMO_SCRIPT, POST_DRAFT | **feature freeze 10 PM** |
| Sat 10 PM to Sun Nov 1, ~10 AM | you: demo video, screenshots, publish | buffer until 12:29 PM |
