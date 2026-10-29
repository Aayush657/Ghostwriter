# Ghostwriter: the ghost that keeps your stories

> A ghost lives in your laptop. Tell it your stories and it writes them down,
> keeps them, and haunts you with them later.

Ghostwriter is a memory keeper with a spooky skin and a warm heart. You tell it a story out loud: a
family recipe, a strange night in the hostel, a letter nobody can explain. A resident ghost, **the
Archivist**, writes it down, keeps it on a candle wall, asks about the parts you left out, and
answers questions about your stories without ever making things up.

Everything runs on your own laptop with open models: **Gemma 4** (through Ollama), **Whisper**
(through faster-whisper) and **Piper**. Turn the Wi-Fi off and it still works.

Built for the DEV **Hacktoberfest Open-Source AI Challenge, Week 4: "Ghost in the Machine"**.

<!-- TODO(you): add screenshots or a GIF here, e.g. docs/screenshots/candle-wall.png -->
_Screenshots and a demo video: [PLACEHOLDER]_

## What it does

- **Listens.** Record in the browser or upload a voice note (wav, mp3, m4a, webm, ogg). Whisper
  transcribes it with automatic language detection: Hindi, English, or the mix in between.
- **Remembers.** Gemma 4 turns each transcript into validated JSON: a title, a 2-3 sentence summary,
  people, places, eras, mood, keepsakes (objects, recipes, sayings), and 2-4 follow-up questions.
- **Unfinished business.** After each story the ghost raises the gaps it noticed. Answer by voice and
  the answer is kept as a linked follow-up story.
- **Seance.** Ask the archive a question. It searches your stories (SQLite FTS5), and Gemma answers
  only from what it found, citing and linking each story. If nothing matches, Gemma isn't asked:
  *"That memory was never given to me."*
- **Ghost handwriting.** Gemma's words stream to the page as they are generated and fade in like ink,
  in a handwriting font.
- **Candle wall.** Every story is a candle on a wall strung with orange and white lights, under a
  moonlit sky with bats, fog and a haunted house (decoration only; plain mode hides it, and it holds
  still for reduced motion). Each story's mood picks its candle and flame colour: a dripping pillar,
  a twisted taper, a lantern, a skull, a jack-o'-lantern or a clay diya. Flames dim a little when a
  story goes unvisited, and relight when you open it. Filter by person, place or era.
- **Whispers.** On launch the ghost sometimes murmurs a line from one of your most faded stories.
- **Ghost voice.** The Archivist can speak, using Piper text-to-speech with ffmpeg effects (lower
  pitch, an echoing room, a faint chorus). Optional.
- **Haunted retelling.** One click retells a memory as a campfire bhoot-kahani. It is labelled as a
  retelling and stored separately; the original is never changed.
- **Memory book.** Export every story as one self-contained HTML file to print, save as PDF, or keep.
- **Plain mode.** One switch for neutral wording and no effects.

It does **not** clone anyone's voice. To hear the storyteller, you play back their original
recording.

## Quick start (Windows)

You need Python 3.11+ (python.org), ffmpeg and Ollama.

```powershell
winget install --id Gyan.FFmpeg -e
winget install --id Ollama.Ollama -e
ollama pull gemma4:e4b
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
```

`setup.ps1` creates `.venv`, installs the pinned packages, downloads the Whisper weights and the
Piper voice, and runs the self-check. It is the only step that needs the internet, apart from the
installs and the model pull above.

If winget's download fails (it did on the development machine with `0x80072eff`), run
`winget show --id <id> -e`, download the installer URL it lists with `curl.exe`, compare the SHA256
it lists, and run the installer yourself.

Check everything (with Wi-Fi off, if you like):

```powershell
.venv\Scripts\python.exe -m ghostwriter.selfcheck --ping
```

## Run

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run.ps1    # your real archive, in data\
powershell -ExecutionPolicy Bypass -File scripts\demo.ps1   # 4 fictional sample stories, in demo-data\
```

Open http://127.0.0.1:8000. The server listens on `127.0.0.1` only, so nothing else on your network
can reach it. The first run of `demo.ps1` asks Gemma to analyse the samples (about half a minute each).

### Ghost voice (optional)

1. Download `piper_windows_amd64.zip` from the
   [Piper 2023.11.14-2 release](https://github.com/rhasspy/piper/releases/tag/2023.11.14-2) and unzip
   it, for example to `C:\Users\<you>\Tools\piper`.
2. Add `GW_PIPER_BIN=C:\Users\<you>\Tools\piper\piper.exe` to `.env` (or put that folder on PATH).
3. `scripts\setup.ps1` downloads the voice (`en_GB-northern_english_male-medium`) into `models\piper\`.

Without Piper, everything else works and the "speak" buttons don't appear.

## Offline and private

- Ghostwriter makes no requests outside `127.0.0.1`. Fonts, scripts and styles are bundled; there are
  no CDNs, analytics, accounts or external APIs. (In the browser's network panel, every request goes
  to the local server.)
- Gemma runs in Ollama on this machine. Whisper and Piper load their weights from disk.
- The self-check reports which local services are up, at startup, in the page, and on the command line.
- Honest note: the **Ollama** server program itself, when online, asks ollama.com for model
  recommendations and logs a warning when it can't. That is Ollama's behaviour, not Ghostwriter's, and
  it doesn't affect anything with the network off.

### Where your data lives

| What | Where |
|---|---|
| Stories, transcripts, tags, questions (SQLite) | `data\ghostwriter.db` |
| Original and normalised recordings | `data\audio\` |
| Cached ghost-voice audio | `data\tts\` |
| Whisper and Piper weights | `models\whisper\<size>\`, `models\piper\` |
| Gemma weights | Ollama's model folder (`%USERPROFILE%\.ollama\models`, or wherever `OLLAMA_MODELS` points) |

`data\`, `demo-data\` and `models\` are git-ignored. Avoid keeping the project inside a cloud-synced
folder (such as OneDrive) if your recordings should stay on this machine.

## Architecture

```
 Browser  (plain HTML/CSS/JS from 127.0.0.1, fonts bundled)
   |  record / upload                     ^  Server-Sent Events: tokens become "ghost handwriting"
   v                                      |
 FastAPI (uvicorn) ------------------------+
   |
   |-- pipeline.py   one job at a time; each step saved before the next; retry resumes
   |     |-- audio.py       ffmpeg -> 16 kHz mono WAV (the original is kept for playback)
   |     |-- transcribe.py  faster-whisper, CPU int8, language auto-detected
   |     '-- llm.py         Ollama /api/chat -> Gemma 4, JSON schema + validation + one repair
   |-- db.py         SQLite: stories, entities, questions; FTS5 trigram index (Hindi + English)
   |-- search.py     BM25 retrieval for the Seance
   |-- prompts.py    every prompt and the Archivist's persona, in one place
   |-- tts.py        Piper -> ffmpeg ghost effects -> cached WAV
   |-- whispers.py   lines from the most faded stories
   |-- export.py     the self-contained memory book
   '-- selfcheck.py  which local services are available
```

[HOW_IT_WORKS.md](HOW_IT_WORKS.md) explains the design decisions in plain language.

## Measured performance

Intel i7-13620H, 16 GB RAM, integrated graphics only (everything on the CPU):

| What | Result |
|---|---|
| Whisper `small` int8 | about 35 s per minute of audio (46 s clip in 25-30 s) |
| Gemma 4 e4b generation | 11-14 tokens/s; 15.8 s to load the model cold |
| Analysing one story (JSON) | 27-36 s |
| Seance answer | first words after 7-19 s, complete in 11-26 s (0.7 s to first word when the same stories were asked about again, thanks to Ollama's prompt cache) |
| Ghost voice | 11.2 s of speech made in 1.2 s; cached repeats are instant |
| Haunted retelling | about 30 s to write ~140 words |

<!-- TODO(you): add Whisper timing and accuracy on your own Hindi/Hinglish recording. -->

## Limitations

- **It is slow on a CPU.** A Seance answer takes seconds to start. Streaming makes the wait feel like
  part of the ritual, but it is still a wait. `gemma4:e2b` is faster and less articulate.
- **Search is keyword-based** (FTS5), not semantic. "Dessert" won't find a story that only says
  "kheer". Tags written by Gemma (names, places, objects) catch many cross-language cases, but not all.
- **Whisper `small` mishears names** (a test clip turned "Shimla" into "Chimla"). `medium` is more
  accurate and slower; it is one line in `.env`.
- **Gemma's follow-up questions are sometimes slightly off**, e.g. asking about a song the
  grandmother "mentioned" when the storyteller only heard humming.
- **The ghost speaks English.** Hindi stories are summarised and answered in English; the voice is an
  English Piper voice.
- **Windows first.** The scripts are PowerShell. The Python code uses `pathlib` and should run
  elsewhere, but only Windows has been tested.
- **Single user, no login.** It binds to `127.0.0.1` for that reason.
- **Piper's GitHub repository is archived;** the 2023 Windows build still works.

## Configuration

Copy `.env.example` to `.env`. Model names, paths and feature flags (ghost voice, plain mode by
default) are documented there, with the prefix `GW_`.

## Development

```powershell
.venv\Scripts\python.exe -m pytest                        # 55 tests; Gemma and Whisper are faked
.venv\Scripts\python.exe -m ghostwriter.transcribe a.wav  # Whisper timing on one file
.venv\Scripts\python.exe -m ghostwriter.tts "Hello"       # the ghost voice on one line
```

[PROGRESS.md](PROGRESS.md) is the build log: decisions, known issues and every measurement.
[PLAN.md](PLAN.md) is the original plan.

## Memory book export

"Open the memory book" on the candle wall (or `/api/book`) gives every finished story as one
self-contained HTML page: fonts embedded, nothing fetched from anywhere. Print it, save it as PDF, or
keep the file; it opens in any browser without Ghostwriter. Recordings stay in `data\audio\`.
From the command line: `.venv\Scripts\python.exe -m ghostwriter.export memory-book.html`.

## Landing page (.tech)

`docs/` is a small static site (no build step, fonts bundled) for the project's .tech domain.
`docs/book.html` is a real memory book made from the four fictional samples, so visitors can read
the ghost's output. To remake it (the exporter refuses to put real stories in `docs/`):

```powershell
$env:GW_DATA_DIR = "demo-data"; .venv\Scripts\python.exe -m ghostwriter.export docs\book.html
```

1. In `docs/index.html`, replace `YOUR_GITHUB_REPO_URL` (twice) and the demo-video box (`TODO(you)`).
2. Push the repo to GitHub, then **Settings > Pages > Deploy from a branch > `main` / `/docs`**.
3. Claim the free .tech domain at hacktoberfest.com/my/promos (free for the first year; it renews at a
   cost, so check the auto-renew setting).
4. In **Settings > Pages > Custom domain**, enter the domain (GitHub adds `docs/CNAME`). At the
   domain's DNS, point `www` (CNAME) to `<your-username>.github.io` and the bare domain (A records) to
   GitHub Pages' addresses `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`.
   Then tick **Enforce HTTPS**.

## Credits

Every model, library, font and tool this project relies on:

| Piece | By | Licence |
|---|---|---|
| Gemma 4 (`gemma4:e4b`) | Google DeepMind | Apache 2.0 (checked with `ollama show gemma4:e4b --license`) |
| Ollama | Ollama | MIT |
| Whisper model weights | OpenAI (CTranslate2 conversion by SYSTRAN) | MIT |
| faster-whisper | SYSTRAN | MIT |
| Silero VAD (bundled in faster-whisper, skips silence) | Silero Team | MIT |
| CTranslate2 | OpenNMT | MIT |
| Piper text-to-speech (2023.11.14-2, run as a separate program) | Michael Hansen / Rhasspy | MIT |
| espeak-ng (bundled inside Piper, for phonemes) | espeak-ng contributors | GPL-3.0 |
| ONNX Runtime (inside Piper and faster-whisper) | Microsoft | MIT |
| Voice `en_GB-northern_english_male-medium` | Piper voices (rhasspy/piper-voices), trained on [OpenSLR 83](http://www.openslr.org/83/) | CC BY-SA 4.0 |
| FFmpeg (gyan.dev full build, run as a separate program) | FFmpeg developers | GPL-3.0 |
| SQLite with FTS5 | SQLite developers | Public domain |
| FastAPI | Sebastián Ramírez | MIT |
| Uvicorn | Encode | BSD-3-Clause |
| httpx | Encode | BSD-3-Clause |
| pydantic, pydantic-settings | Pydantic | MIT |
| python-multipart | Andrew Dunham, Marcelo Trylesinski | Apache 2.0 |
| pytest | pytest-dev | MIT |
| Caveat font | The Caveat Project Authors | SIL Open Font License 1.1 |
| IM Fell English font | Igino Marini | SIL Open Font License 1.1 |

The four sample stories in `samples/` are fictional and were written for this project.

Built with AI assistance: I worked with Claude Code (Anthropic) as a pair programmer throughout.

## Licence

MIT for this project's code (see [LICENSE](LICENSE)). Models, tools, fonts and the voice keep their
own licences, listed above.

## Commits after the deadline

None. Any commit after Oct 31, 2026, 11:59 PM PDT (Nov 1, 12:29 PM IST) will be listed here.
