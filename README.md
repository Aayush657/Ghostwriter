# Ghostwriter: the ghost that keeps your stories

> A ghost lives in your laptop. Tell it your stories and it writes them down,
> keeps them, and haunts you with them later.

Built for the DEV **Hacktoberfest Open-Source AI Challenge, Week 4: "Ghost in the Machine"**.
Everything runs on your own machine with open models: **Gemma 4** (via Ollama) and
**Whisper** (via faster-whisper). Turn the Wi-Fi off and it still works.

> **Status:** work in progress. See [PROGRESS.md](PROGRESS.md).

## What it does

<!-- TODO Stage 6: short feature list + screenshots/GIF -->
_[Screenshot placeholder]_

## Setup (Windows)

<!-- TODO Stage 6: verify these steps on a clean run -->
1. Install system tools (one time):
   - Python 3.11+ from python.org
   - ffmpeg: `winget install --id Gyan.FFmpeg -e`
   - Ollama: `winget install --id Ollama.Ollama -e`
   - If winget's download fails (it did on the dev machine with `0x80072eff`), download the same
     installer URL shown by `winget show --id <id> -e` with `curl.exe`, check its SHA256, and run it.
2. Pull the model: `ollama pull gemma4:e4b` (about 5.5 GB; `gemma4:e2b` is lighter)
3. From the project folder: `powershell -ExecutionPolicy Bypass -File scripts\setup.ps1`
   (creates `.venv`, installs pinned packages, downloads the Whisper weights, runs the self-check)
4. Check everything: `.venv\Scripts\python.exe -m ghostwriter.selfcheck --ping`

### Ghost voice (optional)

The Archivist can speak its answers with [Piper](https://github.com/rhasspy/piper), an offline
neural text-to-speech program, followed by ffmpeg effects (lower pitch, an echoing room, a faint
chorus). Without it, everything else works and the "speak" buttons simply don't appear.

1. Download `piper_windows_amd64.zip` from the
   [Piper 2023.11.14-2 release](https://github.com/rhasspy/piper/releases/tag/2023.11.14-2) and unzip
   it, e.g. to `C:\Users\<you>\Tools\piper`.
2. Put `GW_PIPER_BIN=C:\Users\<you>\Tools\piper\piper.exe` in `.env` (or add that folder to PATH).
3. `scripts\setup.ps1` downloads the voice (`en_GB-northern_english_male-medium`) into `models\piper\`.

## Run

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run.ps1    # your real archive (data\)
powershell -ExecutionPolicy Bypass -File scripts\demo.ps1   # fictional samples in demo-data\
```

Then open http://127.0.0.1:8000. The server listens on `127.0.0.1` only, so other devices on
your network can't reach it.

## Offline proof

<!-- TODO Stage 6: Wi-Fi-off demo clip + self-check output -->
- Ghostwriter itself makes no requests outside `127.0.0.1`: no CDNs (fonts, JS and CSS are bundled),
  no analytics, no external APIs.
- Run `.venv\Scripts\python.exe -m ghostwriter.selfcheck --ping` with Wi-Fi off to see every local
  service answer.
- Honest note: the **Ollama** server program, when it is online, tries to fetch model
  recommendations from ollama.com and logs a warning if it can't. That's Ollama's own behaviour, not
  Ghostwriter's, and it has no effect on Ghostwriter with the network off.

## Where your data lives

Everything stays in this project folder on your disk:

| What | Where |
|---|---|
| Stories, transcripts, tags (SQLite) | `data/ghostwriter.db` |
| Original and normalised recordings | `data/audio/` |
| Whisper weights | `models/whisper/<size>/` |
| Gemma weights | Ollama's model folder (`%USERPROFILE%\.ollama\models` by default, or `OLLAMA_MODELS`) |

`data/` and `models/` are git-ignored. Nothing is uploaded anywhere.

## Architecture

See [PLAN.md](PLAN.md) for now. <!-- TODO Stage 6: diagram here -->

## Configuration

Copy `.env.example` to `.env`. Model names, paths and feature flags are documented there.

## Tests

```powershell
.venv\Scripts\python.exe -m pytest
```

## Credits

<!-- Keep this complete: every model, library, font, sound and asset. -->
| Piece | By | Licence |
|---|---|---|
| Gemma 4 (`gemma4:e4b`) | Google DeepMind | Apache 2.0 (checked with `ollama show gemma4:e4b --license`) |
| Ollama | Ollama | MIT |
| Piper text-to-speech (release 2023.11.14-2, run as a separate program) | Michael Hansen / Rhasspy | MIT |
| espeak-ng (bundled inside Piper, used for phonemes) | espeak-ng contributors | GPL-3.0 |
| ONNX Runtime (bundled inside Piper) | Microsoft | MIT |
| Voice `en_GB-northern_english_male-medium` | Piper voices (rhasspy/piper-voices), trained on [OpenSLR 83](http://www.openslr.org/83/) | CC BY-SA 4.0 |
| Caveat font | The Caveat Project Authors | SIL Open Font License 1.1 |
| IM Fell English font | Igino Marini | SIL Open Font License 1.1 |
| Whisper model weights | OpenAI (CTranslate2 conversion by Systran) | MIT |
| faster-whisper | SYSTRAN | MIT |
| CTranslate2 | OpenNMT | MIT |
| FFmpeg (gyan.dev build) | FFmpeg developers | GPL-3.0 (full build) |
| FastAPI | Sebastián Ramírez | MIT |
| Uvicorn | Encode | BSD-3-Clause |
| httpx | Encode | BSD-3-Clause |
| pydantic / pydantic-settings | Pydantic | MIT |
| SQLite (FTS5) | SQLite developers | Public domain |

Built with AI assistance (Claude Code).

## Licence

MIT for this project's code. See [LICENSE](LICENSE). Models and tools keep their own licences (above).

## Commits after the deadline

None yet. Any commit after Oct 31, 2026, 11:59 PM PDT will be listed here.
