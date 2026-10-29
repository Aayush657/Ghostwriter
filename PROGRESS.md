# PROGRESS

_Last updated: Thu Oct 29, 2026_

**Name decided: Ghostwriter**, subtitle "the ghost that keeps your stories" (user's choice, Oct 28).

## Current stage

- **Stage 0 (setup): DONE.** Self-check all green with a live Gemma reply.
- **Stage 1 (core pipeline): DONE with a synthetic clip.** Waiting on one thing only the user can do:
  a **real recording** (ideally Hindi or mixed), to close Stage 1 formally and test the mic.
- **Stage 2 (Seance, Archivist, handwriting stream, Unfinished Business): DONE**, verified with real Gemma.
- **Stage 3 (candle wall, whispers, browser recording, polish): DONE**, except a real mic test (the
  browser pane blocks the mic). Polish: subtitle, favicon, back link, processing hint, samples fade by
  days unvisited; no horizontal overflow at 375 px; every request goes to localhost.
- **Stage 5: DONE.**
  - Haunted retelling (verified with real Gemma: faithful, eerie, no invented tragedy; stored in its
    own column, original untouched; read aloud as ~60 s of ghost voice).
  - Memory book export: `/api/book`, one self-contained HTML (fonts embedded, 807 KB for the 4 samples),
    prints to PDF; checked in the browser pane, Hindi renders.
  - Landing page in `docs/` for GitHub Pages + .tech domain; no external requests, fine at 375 px.
  - Oct 29: `docs/book.html`, the memory book of the 4 fictional samples (real Gemma output: 2 reactions,
    1 retelling), linked from the landing page ("Read what it wrote"). Added because the .tech prize
    asks for the project to be "live" on the domain, and the app itself can't run on a server.
    `python -m ghostwriter.export <file>` CLI; it refuses to write real stories into `docs/` (tested).
    Checked in the browser pane: 4 stories, fonts load, zero network requests, no overflow at 375 px.
    **User TODOs in `docs/index.html`**: `YOUR_GITHUB_REPO_URL` (x2) and the demo-video box.
- **Stage 6: DONE (drafts).** README complete (quick start **verified on a fresh clone**: setup.ps1 OK in
  43 s, 47 tests pass + 1 skipped without Piper). DEMO_SCRIPT.md (2:00 + 1:30 cut). POST_DRAFT.md in the
  official template (~2,270 words, 13 `PLACEHOLDER`s only the user can fill). HOW_IT_WORKS.md updated.
- **Remaining work is the user's** (see next actions). Code is feature-complete for P0-P2.
- **Stage 4 (ghost voice): DONE.** Piper + ffmpeg effects, cached, optional; "Let the Archivist speak"
  buttons on Seance answers and reactions. `/api/speak` returns 200 in the browser pane; **how it sounds
  is not verified** (no audio here) -> user to listen and judge.

## What works (verified for real)

- Self-check: Python, SQLite FTS5 (trigram), ffmpeg, Ollama, gemma4:e4b, Whisper small all OK.
- Pipeline on a 46 s synthetic English clip (Windows SAPI voice): ffmpeg -> Whisper -> Gemma JSON ->
  SQLite. Accurate title/summary/entities/questions.
- Graceful failure: with the model missing, the story kept its transcript, showed
  "Run: ollama pull gemma4:e4b", and the retry finished it.
- Demo archive (`demo-data\`): all 4 fictional samples (2 English, 2 Hindi/code-mixed) analysed by Gemma.
  Hindi handled well: English summaries, "Nani (grandmother)", "अस्सी के दशक" -> "1980s".
- Seance (real Gemma): correct, cited answers; refuses with "That memory was never given to me." when the
  answer isn't in the stories (tested: grandmother's name, "was it my grandfather's ghost"); English
  question finds a Devanagari story via tags ("What did Nani cook?"); a Devanagari question works too.
- Archivist reaction streams into the story page in the handwriting font; citations become story links.
- Candle wall fades by days unvisited and relights on open (checked in the browser pane); filter works.
- Mic-denied path shows the in-character message plus fix (browser pane blocks the mic).
- `pytest`: 39 pass (DB, FTS + migration, search, JSON repair, Seance/reaction SSE, API, samples,
  whispers, real ffmpeg).

## In progress (next actions)

1. **User**: record a real 1-2 min story in their own browser (`scripts\run.ps1`, then
   http://127.0.0.1:8000, "Speak, and the ghost will listen"). Then check `data\` result together,
   measure Whisper on real Hindi/mixed speech, and consider `medium` if accuracy is poor.
2. **User**: listen to the ghost voice and say if the effect is too strong or too weak
   (knob: `GHOST_EFFECTS` in `ghostwriter/tts.py`).
3. **User**: record the demo video (DEMO_SCRIPT.md), take 3 screenshots, and if possible the "real
   moment" with a family member.
4. **User**: push to GitHub, enable Pages from `/docs`, claim the .tech domain (README > Landing page);
   fill `YOUR_GITHUB_REPO_URL` and the video box in `docs/index.html`.
5. **User**: fill every `PLACEHOLDER` in POST_DRAFT.md, re-read it aloud in your own voice, publish.
6. Me, after the user's recording: measure Whisper on real Hindi/Hinglish, try `medium` if needed, put
   the numbers in README / POST_DRAFT / docs, tune the ghost voice if asked.

## Known issues

- **winget downloads fail** here (`InternetOpenUrl() failed 0x80072eff`). Workaround: curl.exe + SHA256
  from `winget show` + run the installer. GitHub raw/API also resets or rate-limits sometimes; use
  `curl --retry 8 --retry-all-errors`.
- **Hugging Face Xet download stalls.** Workaround: `HF_HUB_DISABLE_XET=1` (in `scripts/setup.ps1`).
- New PATH entries only show up in new terminals; `.env` sets `GW_FFMPEG_BIN` to the full path.
- `Start-Process -Wait` on OllamaSetup.exe hangs (it waits for the tray app). Don't use `-Wait`.
- Ollama reloads the model if `num_ctx` differs between calls (~15 s). Everything now uses `GW_LLM_NUM_CTX`.
- Ollama's own server contacts ollama.com for "model recommendations" when online (logged warning when
  not). Not our code; noted honestly in the README.
- Whisper heard "Shimla" as "Chimla" on the synthetic clip.
- Seance latency on CPU: 7-19 s to first word (prompt evaluation of up to 3 stories).

## Decisions (and why)

- **Project at `C:\Users\aayus\Projects\ghostwriter`**, not the OneDrive Desktop: OneDrive would sync
  private recordings to the cloud.
- **System tools under `C:\Users\aayus\Tools\`**: `ffmpeg\bin`, `Ollama\`, `ollama-models\`
  (user env var `OLLAMA_MODELS`). User asked for one well-defined folder.
- **gemma4:e4b** (Apache 2.0, 7.5B total / 4B effective, Q4_K_M): newest Gemma; 12B+ too slow on CPU.
  Fallback `gemma4:e2b`. `think: false` for direct answers.
- **Whisper small int8, default 4 threads**: 8 or 12 threads were slower.
- **FTS5 trigram tokenizer**, plus a `tags` column (people/places/eras/keepsakes) so Latin-script names
  find Devanagari stories. Index is rebuilt automatically when its columns change.
- **Gemma writes title/summary in English, summaries addressed to "you"**: English search works on Hindi
  stories, and the Seance copies the second person instead of "the speaker".
- **Seance never calls Gemma when nothing matches**; only citations of retrieved stories become links.
- **Jobs run one at a time**; each step saves before the next; crashed jobs become retryable.
- **Unfinished-business questions stored neutral**; the voice is applied when presenting them.
- **Samples are text-only and live in `demo-data\`**; the seeder refuses to touch `data\`.
- **Whispers use the storyteller's own words** (no LLM), from the 3 most faded stories.
- **Fonts bundled locally** (Caveat, IM Fell English, both SIL OFL 1.1, licence files beside them).
- **Dev testing uses a separate data folder** (scratchpad `dev.env`), never `data\`. My preview
  servers use ports 8001/8002 so they never clash with the user's `run.ps1` on 8000.
- **Piper voice `en_GB-northern_english_male-medium`**: chosen for its clear CC BY-SA 4.0 licence
  (ryan and semaine are non-commercial; alan's licence is unclear). Piper 2023.11.14-2 (MIT, archived
  repo) runs as a separate program; espeak-ng inside it is GPL-3.0, credited.
- **Piper's raw audio is piped straight into ffmpeg** (no temp files: Piper failed to write to a
  ~250-character path). Results cached in `data\tts\` by text hash; citation marks are stripped.
- **The Archivist must never sound like a machine** (Gemma once said "memory banks").

## Environment

| Item | Value |
|---|---|
| OS | Windows 11 Home 10.0.26200 |
| CPU / RAM / GPU | i7-13620H (10C/16T), 15.7 GB, Intel UHD only (no CUDA) |
| Python | 3.11.0 (python.org), SQLite 3.38.4 |
| ffmpeg | 9.0.2 full build (gyan.dev), `C:\Users\aayus\Tools\ffmpeg\bin` (has rubberband, aecho, chorus) |
| Ollama | 0.40.12, `C:\Users\aayus\Tools\Ollama`, models in `C:\Users\aayus\Tools\ollama-models` |
| LLM | `gemma4:e4b` (6.6 GB on disk, Apache 2.0) |
| Whisper | faster-whisper 1.2.1, `small`, int8, `models/whisper/small` |
| Piper | 2023.11.14-2, `C:\Users\aayus\Tools\piper\piper.exe` (zip SHA256 F3C58906...EFCEA) |
| Voice | `models/piper/en_GB-northern_english_male-medium.onnx` (CC BY-SA 4.0) |

## Commands

```powershell
cd C:\Users\aayus\Projects\ghostwriter
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1          # one-time setup
powershell -ExecutionPolicy Bypass -File scripts\run.ps1            # real archive -> http://127.0.0.1:8000
powershell -ExecutionPolicy Bypass -File scripts\demo.ps1           # demo archive (fictional samples)
.venv\Scripts\python.exe -m ghostwriter.selfcheck --ping             # check services + Gemma speed
.venv\Scripts\python.exe -m pytest                                   # tests
.venv\Scripts\python.exe -m ghostwriter.transcribe some.wav          # Whisper benchmark
```

## Measurements (real, this machine; numbers for the post)

| What | Result | Notes |
|---|---|---|
| Whisper small int8 | 46.3 s of audio in 25-30 s (about 33-39 s per minute of audio) | synthetic English clip, 4 threads |
| Whisper model load | 2.1 s | |
| Gemma e4b generation | 11.1-13.9 tokens/s | CPU only |
| Gemma e4b cold load | 15.8 s | first call after start |
| Story analysis (JSON) | 26.9 s warm (488 prompt tokens, 182 generated); 143 s for 4 samples (~36 s each) | |
| Seance | first word 7-19 s, full answer 11-26 s | up to 3 stories as context |
| Seance, same stories again | first word 0.7 s | Ollama prompt cache |
| Downloads | Gemma 6.6 GB took ~35 min at ~3.9 MB/s | setup cost, once |
| Piper synthesis | real-time factor 0.066 (9.6 s of speech in 0.63 s) | plain voice |
| Ghost voice end to end | 11.2 s of speech in 1.22 s (Piper + ffmpeg effects); cached repeat 0.00 s | |
| Haunted retelling | ~25-30 s to write 140 words (streamed); read aloud as 60.5 s of ghost voice | browser pane timing |
