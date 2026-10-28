# PROGRESS

_Last updated: Wed Oct 28, 2026, ~16:15 IST_

## Current stage

**Stage 0: setup.** In progress.

## What works (verified)

- Repo, `.gitignore`, MIT licence, README skeleton, PLAN.md.
- Python 3.11.0 venv at `.venv`, pinned `requirements.txt` installed.
- `ghostwriter/config.py` (settings from `.env`, prefix `GW_`).
- `ghostwriter/selfcheck.py`: checks Python, SQLite FTS5 + trigram, ffmpeg, Ollama + model, Whisper weights, Piper (optional). `--ping` asks Gemma for a line and reports tokens/s.
- `pytest`: 4 tests pass (no models needed).

## In progress (next action)

1. curl downloads of `OllamaSetup.exe` v0.40.12 and `ffmpeg-9.0.2-full_build.zip` into `C:\Users\aayus\Tools\_downloads`, SHA256 checked against winget's manifest.
2. Install Ollama to `C:\Users\aayus\Tools\Ollama` (`/DIR=`), unzip ffmpeg to `C:\Users\aayus\Tools\ffmpeg`, add its `bin` to user PATH.
3. Whisper `small` download to `models/whisper/small` (with `HF_HUB_DISABLE_XET=1`).
4. `ollama pull gemma4:e4b`, then `python -m ghostwriter.selfcheck --ping`. Record tokens/s.
5. Commit, mark Stage 0 done, start Stage 1 (`audio.py`, `transcribe.py`).

## Known issues

- **winget downloads fail** on this machine: `InternetOpenUrl() failed 0x80072eff` (connection reset) for GitHub release assets. curl.exe downloads the same URLs fine. Workaround: download with curl, verify the SHA256 from `winget show`, run the installer manually.
- **Hugging Face Xet download stalled** (model.bin stuck at 0 bytes for 10 min). Workaround: `HF_HUB_DISABLE_XET=1` (plain HTTPS). Baked into `scripts/setup.ps1`.

## Decisions (and why)

- **Project at `C:\Users\aayus\Projects\ghostwriter`**, not the OneDrive Desktop: OneDrive would sync private recordings to the cloud.
- **All system tools under `C:\Users\aayus\Tools\`** (ffmpeg, Ollama, Ollama models via user env var `OLLAMA_MODELS=C:\Users\aayus\Tools\ollama-models`, Piper later), as the user asked for one well-defined folder.
- **Gemma 4 `e4b`** as default: newest Gemma (Apr 2026); CPU-only laptop, so 12B+ is too slow. Fallback `gemma4:e2b` if under ~6 tok/s.
- **Whisper `small` int8** default; benchmark `medium` on a real Hindi clip later.
- **Whisper weights in a plain folder** (`models/whisper/small/model.bin`) instead of the HF cache, so runtime loads by path and never touches the network.
- **pydantic-settings** for config: typed, validated, standard in FastAPI apps.
- **Direct deps pinned** in requirements.txt (not a full freeze) for readability.

## Environment

| Item | Value |
|---|---|
| OS | Windows 11 Home 10.0.26200 |
| CPU / RAM / GPU | i7-13620H (10C/16T), 15.7 GB, Intel UHD only (no CUDA) |
| Free disk | ~80 GB on C: |
| Python | 3.11.0 (python.org), SQLite 3.38.4 |
| git | 2.53.0 |
| Ollama | target v0.40.12, `C:\Users\aayus\Tools\Ollama` |
| ffmpeg | target 9.0.2 full build (gyan.dev), `C:\Users\aayus\Tools\ffmpeg` |
| LLM | `gemma4:e4b` |
| Whisper | faster-whisper 1.2.1, `small`, int8 |

## Commands

```powershell
cd C:\Users\aayus\Projects\ghostwriter
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1   # one-time setup
.venv\Scripts\python.exe -m ghostwriter.selfcheck --ping      # check services
.venv\Scripts\python.exe -m pytest                            # tests
# App: (Stage 1) .venv\Scripts\python.exe -m uvicorn ghostwriter.api.main:app --port 8000
```

## Measurements (real, this machine)

_None yet._
