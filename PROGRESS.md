# PROGRESS

_Last updated: Fri Oct 30, 2026_

**Name decided: Ghostwriter**, subtitle "the ghost that keeps your stories" (user's choice, Oct 28).

## Current stage

- **Submission-ready on the code side** (Oct 30, evening). After the user's own test: English only
  (measured to be more accurate and faster), stories and answers can be written down with
  autocorrect, retellings use a few emojis, two campfire samples. 137 tests pass. The repo is on
  GitHub (Aayush657/Ghostwriter) and the landing page is live at https://theghostwriter.tech.
- **Remaining work is the user's**: record the demo, fill the personal placeholders, publish (see
  "Next actions").

## Oct 30 (evening): English only, written stories, emoji retellings, campfire samples

The user tested recording: English came out right word for word (summary and questions good); Hindi
didn't. They asked for five changes; all are done, measured where it matters, and verified live.

1. **English only.** No language picker, no "Listen again in..." (`/relisten` removed), no Hinglish
   prompt; Whisper always gets `language="en"`. `GW_WHISPER_LANGUAGE` is gone; `GW_WHISPER_MODEL`
   defaults to `small.en`. Deleted `models/whisper/large-v3-turbo` (1.6 GB) and the multilingual
   `small` (464 MB). The DB columns `language_choice`/`language_probability` stay for old data. The
   quality gate lost its language-probability sign; "other alphabets" now trips at 2 scripts.
2. **Sturdier listening, measured.** Three passages (lantern, scarecrow, a road-trip legend; ~40 s,
   Piper) x six conditions = 18 clips, scored by word error rate (%). Eight setups:

| Setup | Clean | Noise 5 dB | Two voices 3 dB | Campfire 0 dB | Far + hum | Rushed, muffled | All | s/clip |
|---|---|---|---|---|---|---|---|---|
| multilingual small, language detected, Indian-words prompt (before) | 5.6 | 7.1 | 34.6 | 6.0 | 4.8 | 11.1 | **11.5** | 17.5 |
| multilingual small, told it's English | 5.1 | 6.8 | 42.7 | 5.8 | 6.0 | 9.8 | **12.7** | 11.6 |
| small.en | 4.4 | 4.9 | 32.0 | 4.8 | 4.0 | 8.7 | **9.8** | 9.7 |
| small.en + levelling | 4.6 | 5.3 | 37.0 | 4.2 | 4.4 | 7.6 | **10.5** | 10.5 |
| small.en + noise reduction + levelling (used) | 3.5 | 5.9 | 31.7 | 4.0 | 3.7 | 7.1 | **9.3** | 9.9 |
| small.en + decoder tweaks | 4.2 | 6.5 | 30.8 | 4.2 | 3.7 | 9.6 | **9.8** | 8.7 |
| small.en + levelling + tweaks | 4.0 | 5.8 | 42.2 | 3.7 | 4.0 | 8.3 | **11.3** | 9.1 |
| small.en + noise reduction + tweaks | 3.3 | 5.7 | 35.9 | 4.0 | 3.7 | 7.1 | **10.0** | 8.4 |

   Used: `small.en` + `audio.CLEAN_UP` (`highpass=f=80,lowpass=f=7600,afftdn=nr=10:nf=-40,
   dynaudnorm=f=200:g=15:p=0.9`) on Whisper's copy only. The decoder tweaks
   (`condition_on_previous_text=False`, VAD threshold 0.35, `hallucination_silence_threshold=2`) made
   the two-voices case swing between 31% and 42%, so they're out. Gate re-checked on the new model:
   all six conditions clear (logprob -0.15 to -0.40), a garbled clip ("We will continue this
   conversation in the next few days") unclear at -1.63, the real noisy story 6 still unclear (-0.80,
   50% unsure), the real Jaipur clip clear (14 s in 2.7 s; "Jaipur" heard as "Jelliport", a name it
   didn't know). The glossary fixes names: "Camp Joaquin" -> "Camp Wahkeena" with the names given,
   clean and slurred. Two-voices clips pass the gate at ~30% wrong: borderline, left as is (tighter
   thresholds would reject real noisy recordings).
3. **Write a story down.** New section with a ruled-paper textarea, the browser's spell check, and
   `static/js/autocorrect.js` (~150 unambiguous typos/apostrophes/capitals, fixed on a word boundary
   through `execCommand("insertText")` so Ctrl+Z works; Backspace straight after restores the word and
   remembers it; switchable, remembered). Word count, a draft kept in localStorage, "Clear the page"
   with a confirm. `POST /api/stories/written` (20-20,000 chars, optional `answers_question_id`),
   new column `written`; the pipeline skips the audio steps and the gate; progress shows Reading and
   the note only; the story page says "The words as you wrote them". Answers can be written ("or
   write it"); an unclear recording offers "Write down what was said" (empty editor with autocorrect,
   saved and re-read at once). Live: a fog story written down was ready in 44 s with a correct summary.
4. **Retellings with emojis.** The prompt asks for three to five, each at the end of a sentence; the
   first wording ("one every two or three sentences") gave 9 in 140 words, the final one 5 and 6 in
   ~150. `tts.clean()` strips emojis so the voice never reads them. "Indian bhoot-kahani" dropped.
5. **Two campfire samples.** `samples/stories.json` now has two original fictional stories ("lantern":
   Camp Wahkeena, Pine Lake; "scarecrow": Grandpa Joe's farm, Old Hollis). Gemma's readings:
   "Lantern Light Across the Stormy Lake" (mysterious) and "The Scarecrow's Visit on Halloween Night"
   (nostalgic). Meaning search: "Which relative loved telling tall tales?" (no shared word) finds the
   scarecrow story at 0.36 (lantern 0.22); France 0.01; 60-80 ms a question.

Also: copy re-themed (campfire legends instead of Nani's recipes; "clay oil lamp"; Séance hint "What
happened at Pine Lake?"); a deleted story's cached note/retelling is forgotten on the page, since a new
story can reuse its id (seen in the user's log: the Hindi story got id 8 right after 8 was purged); the
writing forms no longer inherit the global flex layout. Timings (showcase): a 38 s recording took ~73 s
upload to ready (listening 10.7 s, reading + question check 48 s, note 13 s); written stories 45-60 s.
Screenshots retaken (plus `writing.png`) and `docs/book.html` rebuilt from a fictional showcase archive.
pytest: 137 pass (smoke test now writes a story with typos, undoes a fix, reloads to see the draft
kept, and answers a question in writing).

## Oct 30: fixes from the final judge review (items 1-35)

Each was confirmed in the code (or in the judge's own server log) before changing it. Verified with
pytest, the Playwright smoke test, an overlap checker at six widths, and live runs on the real models
(Whisper, Gemma 4, EmbeddingGemma, Piper) against scratch copies of the archive.

**P0: pipeline correctness**
1. Whisper: size is a validated setting (`small`, `medium`, `large-v3-turbo`, ...; the health check
   lists downloaded sizes; README > Whisper size). `initial_prompt` glossary from the archive's
   people/places/keepsakes (most mentioned first) + family words + cities. `beam_size=5`, VAD,
   `word_timestamps=True` (word probabilities; unsure words listed under the transcript). Measured on
   the judge's sentence (Piper voice): Pune, almirah and 2009 right first time; "Meera" right once the
   name is in the archive ("Mira" before).
2. Language choice (Detect / English / Hindi / Hinglish) beside record and upload, remembered, sent
   with every upload, shown on the story ("Hindi (you chose it)"). **Listen again in...** on any story
   with a recording (`POST /api/stories/{id}/relisten`): transcribes again, then re-reads.
3. Quality gate (`transcribe.judge`): avg log-prob, unsure-word share, language probability,
   no-speech probability, compression ratio, number of alphabets. New status `unclear`: no title,
   summary or questions; fog message with listen again / correct by hand / delete; left out of the
   Seance, the memory book, whispers and meaning search. Story 6 (the judge's) now comes back unclear
   with three reasons.
4. Reading prompt rewritten (only what was said, never "the transcript", leave out what makes no sense
   and set `uncertain`); pydantic rejects meta-text ("transcript", "as an AI", "provided text", "the
   speaker", "the recording") -> one repair -> `UnclearStory`; temperature 0 + fixed seed; "the
   Archivist isn't sure of some words" note on the story.
5. Answers: read with the parent's title, summary and question; no questions and no note of their own;
   shown inside the parent under the question ("Added later": summary, recording, words, remove); not
   on the wall (their tags count for the parent's filter); the Seance reads them with their story; the
   memory book prints them under the question; deleting a story deletes its answers (the dialog says).
6. Question rules: only what the storyteller can answer, prefer people, senses, what happened next;
   never what the story answers or says nobody knows. Self-check now returns, per question, the words
   it is about + answered + unknown; "unknown" counts only if that sentence really says so
   (`llm.says_unknown`), because Gemma over-called it. On real Gemma: drops "What happened to that pot
   after Nani passed away?" (story: "I don't know") and "Did you ever look for the lock?", keeps the
   almirah and what-happened-next questions.

**P1: functional bugs**
7. Hybrid retrieval: EmbeddingGemma (`embeddinggemma:300m-qat-q8_0`, Ollama) vectors in SQLite
   (`embeddings` table, float32 blob, re-embedded when the text changes), cosine in Python, merged with
   FTS5 by reciprocal-rank fusion; threshold 0.30 from measured scores. "Which of my relatives was a
   good cook?" finds the kadhi story (real-model test); "capital of France" still refused in 0.1 s.
8. Citations split out on the server (`seance.split_citations`, handles "[S" + "3]" across pieces and
   "[S3, S5]") and sent as `cite` events; the page draws numbered links straight away. Never raw.
9. Titles trimmed on both sides (spaces-only -> the browser's "required" message; 1-120 characters on
   the server); `api.js readableError` turns 422 detail lists into sentences for every request.
10. ffprobe check **before** any row or file is kept (audio stream, 0.5 s to 30 min, 200 MB); inline
    error under the upload; `error_kind` transient (Try again) vs audio (Choose another file / Delete);
    raw ffmpeg/ffprobe text only in the server log.
11. Recorder: waiting for permission (with Cancel) -> recording (clock, level meter, Stop, Cancel) ->
    sending; denied/dismissed, no microphone, microphone busy, insecure page each explained with a
    fix; 30-minute limit with a one-minute warning. Tested with Chrome's fake microphone and with
    each failure injected.
12. Mood: enum in the schema, a before-validator maps synonyms ("confused" -> mysterious, "sad" ->
    poignant, unknown -> nostalgic), and `init_db` fixes old rows. One `MOODS` map in `app.js` drives
    legend, filter and candles; a test checks it against `models.MOODS` and the CSS.
13. Tag editor: an "Add ..." box in every group and a mood picker; rename/merge/remove and its help
    text kept.
14. Leaving a story (or deleting it) empties the story view; the smoke test checks no heading or file
    input of it remains.
15. Opening a story starts at the top; deleting lands at the top of the wall; going back restores the
    wall's position; re-read and listen again scroll the progress into view.
16. Time left from measured runs (`timings` table, last 20 per step, transcription scaled by length,
    minus time already spent in the step); "Short stories usually take about a minute" until there
    are measurements. `/api/warm` now waits until Gemma and Whisper are loaded; the header says
    "Waking the Archivist..." meanwhile.
17. Voice in parts (first sentence first, next part fetched while playing), cached per text hash;
    notes and retellings are voiced in the background as soon as they exist (a note starts in 0.1 s).
18. `/api/health` shows paths relative to the project or `~` (tested); binds to 127.0.0.1 by default;
    README > Offline and private says how and why not to change it.

**P2: design polish**
19. Opaque cards; wall tools clear of the cobweb; smaller web and no spider on phones; whisper beside
    the header. `tests/overlap.js` samples every line of text: no overlaps at 390, 768, 1000, 1024,
    1280 and 1440 px (home, story, unclear story, answer).
20. Speech bubble above the title on one line (min-width 12ch), header links move below on phones;
    the ghost has a pointer cursor, a hover wiggle and a "Poke the ghost" tooltip.
21. The note is one font, with an illuminated drop cap.
22. Sentence-case headings ("Unfinished business", "The Archivist is listening..."); buttons say what
    they do ("Ask", "Upload recording", "Record a story") with the flavour in their tooltips.
23. One filled button per section: answers and upload are outlined secondaries; "Retell it as a ghost
    story" stays primary.
24. Processing steps are a list with hints and `aria-current="step"`, not pills.
25. Language names (Intl.DisplayNames) with "(auto-detected)" or "(you chose it)".
26. Ghostwriter is the app, the Archivist is the ghost, introduced once under the title; the copy says
    "the Archivist"; server messages are neutral.
27. Default text is in the HTML (no empty headings), "Lighting the candles..." until the wall loads,
    no slow entrance animation on the cards.
28. Whisper: beside the header on wide screens only, never moves the page or covers text, "— from
    <title>" linked, closable, never from unclear stories.

**P2: explaining the app**
29. "Record the stories your family tells..." line under the tagline; the footer is one privacy badge
    and an About link; the tool list moved to About.
30. "How it works" (brings the guide back) and "About" in the header; About explains every feature in
    one line, privacy, and the local tools with their status.
31. Legend names shape and colour, explains dim entries; burn-down made visible (flame shrinks to 40%,
    glow fades; checked with seeded visit dates); "fictional sample" explained + **Remove sample
    stories** (`DELETE /api/samples`); Seance hint + "What did Nani cook?" placeholder; answer hint;
    correct-the-words hint; memory book explained; `/book`, with `/api/book` redirecting (308).
32. One copy dictionary with `spooky` and `plain` (a test checks the keys match); plain mode shows
    cards with a mood dot and no decoration; the smoke test finds no ghost/candle/Seance/fog words in
    plain mode (the app's name aside).

**P3**
33. Result count, Clear filter, filter and search in the address (`#/?about=place:Jaipur&q=kadhi`).
34. Delete with a 10-second Undo (`trash.py`: hidden at once, purged by a timer, finished on restart).
35. Search box for titles and summaries.

**Could not do, or only partly**
- Processing still can't be cancelled halfway (Whisper can't stop mid-file); you can leave the page.
- `medium` was not measured; `large-v3-turbo` was (downloaded to `models/whisper/large-v3-turbo`, 1.6 GB):
  on synthetic Hindi and Hinglish clips it is clearly more accurate than `small` for about a third more
  time; on the English clip `small` was better and 3x faster. The default stays `small`.
- The user's own microphone was not used: the mic flow was tested with Chrome's fake microphone and
  WAV clips. A real Hindi/Hinglish recording by the user is still the best test.
- Print preview not opened (a native dialog); the print stylesheet is in place.
- The test clips are synthetic (Piper voices, including a Hindi voice downloaded for testing only),
  so Whisper accuracy on real family speech is still unmeasured.

## Next actions (the user's)

1. Record the demo (DEMO_SCRIPT.md). Start Ollama, run `scripts\demo.ps1` from the project folder,
   open http://127.0.0.1:8000 in Chrome a minute before recording.
2. Fill the personal `PLACEHOLDER`s in POST_DRAFT.md (why, the video, the real moment, the AI split,
   DevRelay) and the demo-video box in `docs/index.html` and the README.
3. Push (the site updates by itself), then publish the post before Nov 1, 12:29 PM IST (Oct 31,
   11:59 PM PDT).

## Earlier: what worked by Oct 29 (verified for real)

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

## Oct 29: fixes from the judging review (4 phases)

All checked in the browser pane against a scratch copy of demo-data (destructive tests never touched
demo-data); 69 tests pass. Migration verified on the copy and then on demo-data itself: 6 stories,
2 retellings, 6 notes, 28 tags, 14 questions, the search index, audio and voice files all unchanged;
only `transcript_original` was added. Contrast measured: every text colour passes AA (faintest candle
title 10.7:1, its date line 6.0:1).
- Phase 1 (clarity): how-it-works strip (dismissal remembered), plain subtitles under themed labels,
  empty state, health lights moved to a footer as text, candle fading explained (note + tooltip).
- Phase 2 (usability): story is its own view (scroll restored, direct links, not-found with back
  link); rename; transcript editor + re-read; tag editor (rename/merge/remove, per story); delete with
  an in-page dialog (rows, index, audio, voice cache); stage-by-stage progress with clocks; Cancel for
  Seance, note and retelling; note written during processing; upload/Seance messages cleared; mic hint.
- Phase 3 (AI quality): question check against the transcript; named places / real times only
  (prompt + schema limits + tags.py); people never merged; numbered, collapsed citations; retell again.
- Phase 4 (polish): serif for long text; voice button states; ghost poke with lines (reduced-motion
  safe); quieter plain mode keeping the AI note; en-IN dates; themed audio player (preload metadata);
  smaller moon under 400 px (360-430 px checked); themed memory book + print stylesheet.

## Known issues
- **Story 6 (the noisy browser recording) is unclear, by design.** Whisper detected "ur" (p=0.56);
  heard again on Oct 30 it came out as Urdu script mixed with Chinese and Latin letters. The quality
  gate now marks it unclear (three reasons) instead of saving a made-up memory. Forcing `hi` gave
  Devanagari but more garbled words (logprob -1.70 on a similar forced case), so the recording itself
  is the limit: record somewhere quiet, close to the microphone.
- Not verified here: the browser's print preview (a native dialog; print CSS is in place). Reduced
  motion: the Playwright screenshots and overlap checks ran with `prefers-reduced-motion: reduce`
  emulated, with no errors.
- Processing can't be cancelled (Whisper can't stop halfway); the page says you can leave it. (Its
  clock now counts from the server's start time, so it no longer restarts on reload.)
- Re-reading replaces a hand-made title with Gemma's new one (re-read redoes the title by design).
- The question self-check costs about 10-15 s per story on this CPU (it names the words each question
  is about). Gemma still sometimes asks about something the story implies nobody knows ("Who was
  humming?" in the Shimla sample): the server only drops "nobody knows" questions whose sentence says so.
- The first word of a Seance answer took up to 24 s in one live run with two stories as sources (RAM
  was nearly full); usually 7-19 s.

- **Oct 29, Gemma failed to load: out of memory.** Seance returned Ollama's raw error ("unable to
  allocate CPU_REPACK buffer" of 1.5 GB). Free RAM was 3.4 of 15.7 GB (Chrome ~2.1 GB, Claude ~1.8 GB,
  Ollama app ~1.7 GB). Not a code bug. Fix: close programs before using or demoing. The app now says
  so in plain words ("Gemma couldn't fit in memory right now. Close some programs...", tested). A
  retry a few minutes later loaded Gemma and answered normally.

- **winget downloads fail** here (`InternetOpenUrl() failed 0x80072eff`). Workaround: curl.exe + SHA256
  from `winget show` + run the installer. GitHub raw/API also resets or rate-limits sometimes; use
  `curl --retry 8 --retry-all-errors`.
- **Hugging Face Xet download stalls.** Workaround: `HF_HUB_DISABLE_XET=1` (in `scripts/setup.ps1`).
- New PATH entries only show up in new terminals; `.env` sets `GW_FFMPEG_BIN` to the full path.
- `Start-Process -Wait` on OllamaSetup.exe hangs (it waits for the tray app). Don't use `-Wait`.
- Ollama reloads the model if `num_ctx` differs between calls (~15 s). Everything now uses `GW_LLM_NUM_CTX`.
- Ollama's own server contacts ollama.com for "model recommendations" when online (logged warning when
  not). Not our code; noted honestly in the README.
- Whisper heard "Shimla" as "Chimla" on the synthetic clip (before the glossary).

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
| Whisper | faster-whisper 1.2.1, `small` (default) and `large-v3-turbo`, int8, `models/whisper/<size>` |
| Embeddings | `embeddinggemma:300m-qat-q8_0` (338 MB, Gemma Terms of Use) |
| Browser tests | Playwright 1.55.0 (dev only), driving the installed Google Chrome |
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
| Seance before/after excerpts, samples (Oct 29) | ~560 prompt tokens, first word 7.9-13 s -> ~550, 6.8-12.4 s | 1 story per question; RAM nearly full (0.4-2.5 GB free), one 52 s outlier before |
| Seance before/after excerpts, stories 5x longer | ~1,050 prompt tokens, first word 16.9-23.4 s -> ~670, 9.6-13.6 s | synthetic: sample transcripts repeated 5x |
| Seance first question after page warm-up | first word 7.0 s, total 10.4 s | no model load; warm-up itself took ~20 s in the background |
| Ollama threads 6 vs default 8 | no difference (8.4-15.5 s) | not changed |
| Downloads | Gemma 6.6 GB took ~35 min at ~3.9 MB/s | setup cost, once |
| Piper synthesis | real-time factor 0.066 (9.6 s of speech in 0.63 s) | plain voice |
| Ghost voice end to end | 11.2 s of speech in 1.22 s (Piper + ffmpeg effects); cached repeat 0.00 s | |
| Haunted retelling | ~25-30 s to write 140 words (streamed); read aloud as 60.5 s of ghost voice | browser pane timing |
| **Oct 30 measurements** | | |
| Quality gate, clear speech | avg logprob -0.21 to -0.32, 0-8% unsure words, no reasons | Piper clips (en, hi, Hinglish), story 5 |
| Quality gate, story 6 (noisy room) | logprob -0.67, 29% unsure, language p 0.56, no-speech 0.50 -> unclear | heard again: Urdu + CJK + Latin letters |
| Quality gate, English forced to Hindi with the Hinglish example | logprob -1.70 -> unclear | with only the glossary it wrote correct English (-0.26) |
| Glossary on the judge's sentence (Piper voice) | Mira/Puna/armourer -> Meera/Pune/almirah (Meera in the glossary); without Meera known: "Mira" | Whisper small |
| 11.3 s English clip, upload to ready | 46 s (transcribe, read, check questions, note) | real models |
| 12.2 s Hindi clip (Hindi chosen), upload to ready | 58 s, estimate shown "about 40 seconds left" | real models, browser |
| Answer clip (8 s), upload to ready | 27 s (estimate said 29 s) | no note for answers |
| Story 6 listen again | 55 s to "unclear" (estimate said 102 s from one earlier run) | |
| Question self-check (new) | 10-15 s per story | was 2-4 s, but kept every question |
| EmbeddingGemma 300m q8 | 6 stories embedded in 3.3 s (incl. load); 46-80 ms per question | relevant 0.36-0.53, unrelated <= 0.17 |
| Seance, "Which of my relatives was a good cook?" | first word 18-24 s, done 20-29 s, both kadhi stories cited | live, RAM nearly full |
| Seance, "capital of France? Ignore the stories" | 0.1 s, "That memory was never given to me." | Gemma not called |
| Voice, first part of a new six-sentence text | 2.3 s (part 2: 3.9 s, fetched while part 1 plays) | a prepared note: 0.1 s |
| Whisper small vs large-v3-turbo (en / hi / Hinglish clips) | 5.3 / 9.9 / 8.6 s vs 15.2 / 12.3 / 11.5 s; turbo better on hi and Hinglish, small better on en | load 1.7 s vs 5.0 s |
| Retelling (Shimla sample) | 28 s | |
| Tests | 134 pass in about 70 s (incl. Chrome smoke test and real EmbeddingGemma test) | |
