# PROGRESS

_Last updated: Wed Oct 28, 2026, 16:25 IST_

## Current stage

**Stage 0: setup.** Done except the Gemma reply check (model downloading).
**Stage 1: core pipeline.** Code complete and tested with mocks. Verified for real up to Whisper; Gemma step waits for the download.

## What works (verified)

- Repo, `.gitignore`, `.gitattributes`, MIT licence, README skeleton, PLAN.md.
- Python 3.11.0 venv at `.venv`, pinned `requirements.txt`.
- ffmpeg 9.0.2 and Ollama 0.40.12 installed under `C:\Users\aayus\Tools\` (SHA256 verified).
- Whisper `small` weights in `models/whisper/small/`.
- `python -m ghostwriter.selfcheck`: all green except "Gemma model" (downloading).
- **Real run through the API** (synthetic English clip, Windows SAPI voice, 46 s): upload -> ffmpeg -> Whisper -> transcript stored; Gemma step failed with the friendly message "The model gemma4:e4b isn't downloaded. Run: ollama pull gemma4:e4b". Story is retryable and keeps its transcript.
- UI (Stage 1, plain): upload, archive list, story page with audio playback, health pills, retry, "Answer" buttons for unfinished business. Checked in the browser pane.
- `pytest`: 22 pass (DB, FTS, JSON repair, API, real ffmpeg).

## In progress (next action)

1. Wait for `ollama pull gemma4:e4b` (5.5 GB, started 16:15, ~3.9 MB/s).
2. `python -m ghostwriter.selfcheck --ping` -> record tokens/s. Check licence with `ollama show gemma4:e4b --license`.
3. Retry story 1 in the dev data folder -> confirm a tagged story. Record Gemma timings.
4. Ask the user to record a real story (Hindi/English/mixed) -> Stage 1 done.
5. Stage 2: `search.py` (FTS5 bm25), Seance SSE endpoint, Archivist prompts, handwriting font.

## Known issues

- **winget downloads fail** here (`InternetOpenUrl() failed 0x80072eff`). Workaround: curl.exe + SHA256 from `winget show` + run the installer.
- **Hugging Face Xet download stalls.** Workaround: `HF_HUB_DISABLE_XET=1` (in `scripts/setup.ps1`).
- New PATH entries (ffmpeg, Ollama) only appear in **new** terminals. `.env` sets `GW_FFMPEG_BIN` to the full path to be safe.
- `Start-Process -Wait` on OllamaSetup.exe hangs forever (it waits for the tray app it launches). Don't use `-Wait` for it.

## Decisions (and why)

- **Project at `C:\Users\aayus\Projects\ghostwriter`**, not the OneDrive Desktop: OneDrive would sync private recordings to the cloud.
- **System tools under `C:\Users\aayus\Tools\`**: `ffmpeg\bin`, `Ollama\`, `ollama-models\` (user env var `OLLAMA_MODELS`), Piper later. User asked for one well-defined folder.
- **Gemma 4 `e4b`**: newest Gemma (Apr 2026); CPU-only laptop, so 12B+ is too slow. Fallback `gemma4:e2b`.
- **Whisper `small` int8, default 4 threads**: 8 or 12 threads were slower (25 s vs 31 s on the same clip).
- **FTS5 `trigram` tokenizer**: tested; works for Devanagari and English, and matches substrings ("haunt" finds "haunted").
- **Whisper weights in a plain folder**, loaded by path: runtime never touches the network.
- **Jobs run one at a time** (lock in `pipeline.py`) so Whisper and Gemma don't compete for 16 GB RAM.
- **Each pipeline step saves before the next**; retry resumes from the first missing step; crashed jobs become "failed" on restart.
- **Unfinished-business questions are stored neutral**; the Archivist's voice is applied when presenting them, so plain mode stays plain.
- **Gemma writes title/summary in English** even for Hindi stories, so English questions can find Hindi stories in search.
- **Static UI files sent with `Cache-Control: no-cache`** so an updated UI never shows stale JS.
- **Dev testing uses a separate data folder** (`uvicorn --env-file <scratch>\dev.env`), never the real `data/`.

## Environment

| Item | Value |
|---|---|
| OS | Windows 11 Home 10.0.26200 |
| CPU / RAM / GPU | i7-13620H (10C/16T), 15.7 GB, Intel UHD only (no CUDA) |
| Python | 3.11.0 (python.org), SQLite 3.38.4 |
| ffmpeg | 9.0.2 full build (gyan.dev), `C:\Users\aayus\Tools\ffmpeg\bin` |
| Ollama | 0.40.12, `C:\Users\aayus\Tools\Ollama`, models in `C:\Users\aayus\Tools\ollama-models` |
| LLM | `gemma4:e4b` (5.5 GB) |
| Whisper | faster-whisper 1.2.1, `small`, int8, `models/whisper/small` |

## Commands

```powershell
cd C:\Users\aayus\Projects\ghostwriter
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1          # one-time setup
.venv\Scripts\python.exe -m ghostwriter.selfcheck --ping             # check services
.venv\Scripts\python.exe -m pytest                                   # tests
.venv\Scripts\python.exe -m uvicorn ghostwriter.api.main:app --port 8000   # app -> http://127.0.0.1:8000
.venv\Scripts\python.exe -m ghostwriter.transcribe some.wav          # Whisper benchmark
```

## Measurements (real, this machine)

| What | Result | Notes |
|---|---|---|
| Whisper small int8, 4 threads | 46.3 s audio in 25-30 s (about 33-39 s per minute of audio) | synthetic English clip, other downloads running at the time |
| Whisper model load | 2.1 s | |
