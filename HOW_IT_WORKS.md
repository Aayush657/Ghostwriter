# How Ghostwriter works

Plain-language notes on the main design decisions, for the write-up and for interviews.
Each section is: what it does, how, and why this way.

## 1. The big picture

You give the Archivist (the ghost who lives in Ghostwriter) a recording, or a story written down. A
background job turns it into a stored, searchable story:

```
original audio --ffprobe check--> saved --ffmpeg (+ light clean-up)--> 16 kHz WAV --Whisper--> words
written story -------------------------------------------------------------------------> words
  --quality check--> Gemma 4: title, summary, people, places, eras, mood, keepsakes, questions
  --> SQLite (+ full-text index) --EmbeddingGemma--> a meaning vector for the Seance
```

Then you can ask the archive questions (Seance), and the Archivist answers only from your stories,
written out live, word by word.

Everything runs on the laptop. The web page talks only to `127.0.0.1`; the server talks only to
Ollama on `127.0.0.1:11434`; Whisper and Piper load their weights from folders on disk.

## 2. Hearing the words right, and writing them down

Memory accuracy is the whole product, so most of the work goes into the words.

- **English, with the English model.** Whisper always listens in English, with the English-only
  `small.en` (int8). An earlier build offered Hindi and Hinglish; the speech model that runs at a
  usable speed on a CPU got too many Hindi words wrong, so it was taken out, along with the
  multilingual models (2 GB less on disk).
- **A light clean-up first.** ffmpeg makes Whisper's copy of the recording 16 kHz mono and cleans it
  gently: a high-pass at 80 Hz and a low-pass at 7.6 kHz (rumble and hiss outside the voice), mild
  FFT noise reduction (`afftdn`), and volume levelling (`dynaudnorm`). The original stays untouched for
  playback.
- **Chosen by measurement.** Three passages (about 40 s each, read by Piper) were mixed six ways:
  clean; steady pink noise at 5 dB; two other voices talking at 3 dB; a campfire's low rumble and
  crackle at 0 dB; far from the microphone with mains hum; and rushed speech, muffled (a 1.8 kHz
  low-pass, like a phone in a pocket) with room echo. Every setup transcribed all 18 clips; the score
  is the share of words wrong (word error rate), lower is better:

| Setup | Clean | Steady noise | Other voices | Campfire rumble | Far & quiet | Rushed, muffled | All | Seconds per clip |
|---|---|---|---|---|---|---|---|---|
| Before: multilingual `small`, language detected, Indian-words prompt | 5.6% | 7.1% | 34.6% | 6.0% | 4.8% | 11.1% | **11.5%** | 17.5 |
| Multilingual `small`, told it's English | 5.1% | 6.8% | 42.7% | 5.8% | 6.0% | 9.8% | **12.7%** | 11.6 |
| English-only `small.en` | 4.4% | 4.9% | 32.0% | 4.8% | 4.0% | 8.7% | **9.8%** | 9.7 |
| `small.en` + volume levelling | 4.6% | 5.3% | 37.0% | 4.2% | 4.4% | 7.6% | **10.5%** | 10.5 |
| **`small.en` + gentle noise reduction and levelling** (chosen) | 3.5% | 5.9% | 31.7% | 4.0% | 3.7% | 7.1% | **9.3%** | 9.9 |
| `small.en` + decoder tweaks | 4.2% | 6.5% | 30.8% | 4.2% | 3.7% | 9.6% | **9.8%** | 8.7 |
| `small.en` + levelling + decoder tweaks | 4.0% | 5.8% | 42.2% | 3.7% | 4.0% | 8.3% | **11.3%** | 9.1 |
| `small.en` + noise reduction + decoder tweaks | 3.3% | 5.7% | 35.9% | 4.0% | 3.7% | 7.1% | **10.0%** | 8.4 |

  The clean-up helped most on clean, quiet and rushed speech, and cost a little on steady noise. The
  decoder tweaks (no conditioning on earlier text, a looser voice detector, skipping hallucinated
  silences) made the "other voices" case erratic, so they are not used. Other voices talking over the
  storyteller is still the hardest case (about a third of the words wrong); the page suggests
  writing the story down instead.
- **A glossary guides Whisper.** Before listening, Whisper reads a short prompt of the people, places
  and keepsakes already in the archive (most mentioned first). A name it has never heard is the most
  common mistake ("Camp Wahkeena" came out "Camp Joaquin"); with the archive's names in the prompt,
  the same clip came out "Camp Wahkeena", even rushed and muffled. Correct a name once in the tag
  editor and later recordings get it right.
- **Beam search, voice detection and word probabilities.** `beam_size=5`, Silero VAD to skip silence
  (fewer invented words), and `word_timestamps=True`, which gives every word its own probability.
  Words Whisper gave less than even odds are listed under the transcript, so you know what to check.
- **Or write it down.** "Write a story down" is a page of ruled paper (a CSS background that scrolls
  with the text) with the browser's own spell check (red underlines, right-click suggestions) and an
  offline autocorrect (`autocorrect.js`): when you finish a word, a short list of unambiguous typos
  and missing apostrophes is fixed ("teh" -> "the", "dont" -> "don't", "halloween" -> "Halloween";
  real words like "wont" or "its" are never touched), and a word that starts a sentence, a line or
  quoted speech gets its capital, as a phone keyboard would ("Mr.", initials, "e.g." and "..." don't
  end a sentence). The fix goes through the browser's own editing
  command, so Ctrl+Z undoes it, and Backspace straight after puts your word back and leaves it alone
  from then on. It can be switched off, and the draft is kept in the browser if you leave the page. A
  written story (`POST /api/stories/written`, 20 to 20,000 characters) starts with its words, so the
  pipeline skips both audio steps and the quality gate (a person wrote them) and goes straight to
  Gemma; its progress shows only Reading and the note. Answers to the Archivist's questions can be
  written the same way, and a recording lost in fog can be written down instead.

## 3. The quality gate: fog is not a memory

A noisy recording once came back as a mix of Urdu, Chinese and Latin letters, and Gemma dutifully
made it a "memory" ("Unclear Memory Fragment: The transcript provided contains fragmented..."). Now,
between Whisper and Gemma, `transcribe.judge()` looks at Whisper's own confidence:

- average log-probability below -0.8: Whisper was guessing;
- compression ratio above 2.4: a repetition loop (Whisper's own threshold);
- the text came out in another alphabet (English speech never does);
- or two weak signs together: log-probability below -0.55, more than 20% unsure words, or a high
  no-speech probability.

The thresholds come from real recordings: clear speech scores about -0.3 with almost no unsure words;
the noisy room recording scored -0.67 with 29% unsure words. Re-checked with `small.en` and the
clean-up: every test clip above passed (clear speech about -0.15 to -0.26), the real noisy recording
is still unclear (-0.80, half its words unsure), and a garbled clip that Whisper heard as "We will
continue this conversation in the next few days" (a classic Whisper invention) scored -1.63 and was
stopped. A story that fails gets the status **unclear**: no title,
summary or questions are invented, it stays out of the Seance, the memory book and the whispers, and
its page says *"The words came to me as fog..."* with two ways forward: write down what was said
(an empty page with spell check and autocorrect; a person's words skip the check and Gemma reads
them at once), or delete it.

## 4. Never losing a story

- An upload is checked with **ffprobe before anything is saved**: a text file named `.mp3`, a file
  with no sound, a clip under half a second or over 30 minutes is refused under the upload button,
  and no story is created. ffmpeg's own error text goes to the server log, not the page.
- The original upload is then saved **untouched**, named after the story's id (never the uploaded
  name, so a crafted filename can't write elsewhere).
- Each pipeline step **saves its result before the next starts** (WAV, transcript, analysis). If
  Gemma is down, the transcript is already safe.
- Failures say what kind they are. A passing problem (Ollama not running, out of memory, an
  interrupted job) offers **Try again**; a file that can't be read offers **Choose another file**,
  because trying the same file again can't help.
- If the app is killed mid-job, the next start marks that story "interrupted" so it can be retried.
- Jobs run **one at a time** (a lock), so Whisper and Gemma never fight over 16 GB of RAM.
- **Corrections never destroy.** Editing a transcript keeps Whisper's original words in
  `transcript_original`. Re-reading reruns Gemma on the corrected words but keeps the recording, the
  retelling, and every answered question.
- **Deleting asks first, and can be undone.** The story disappears at once, and a notice offers
  **Undo** for 10 seconds; only then are its rows, search entry, recordings and voice files removed
  (`trash.py`; a restart finishes any deletion that was pending). Answers added to the story go with
  it, and the dialog says how many.
- **Database changes are additive**: `init_db()` only adds missing columns and tables, so an older
  archive opens unchanged. Moods from before the fixed list ("confused", "calm") are mapped to the
  nearest candle mood on start.

## 5. Getting reliable, honest JSON out of a small model

Gemma must return title, summary, people, places, eras, mood, keepsakes, questions and an
`uncertain` flag. Four layers make that reliable:

1. **Ollama structured output**: the JSON schema (generated from the pydantic model `StoryAnalysis`)
   is sent as the `format`, so sampling can only produce JSON of that shape. The mood is an enum of
   the six candle moods.
2. **Strict validation**: the same model parses the reply and checks what a schema can't, including
   **no meta-text**: a title, summary or question that talks about "the transcript", "the speaker",
   "the recording" or "as an AI" is rejected. A mood outside the list is mapped to the nearest one
   ("sad" becomes "poignant") rather than drawn with the wrong candle.
3. **One repair attempt**: Gemma sees its own reply and the exact error, once. If it still can only
   describe the words ("the transcription is unintelligible"), the story is **unclear**, not saved.
4. **Temperature 0 and a fixed seed**: re-reading the same words gives the same title, mood and tags.

The prompt says: describe only what the storyteller says, never add names, places, dates, reasons or
feelings, and if some words make no sense, leave them out and set `uncertain`; the story page then
says *"The Archivist isn't sure of some words, so it left them out."*

Then two tidy-ups:

- **Tags** (`tags.py`, tested): a place must have a name ("Pine Lake", "Grandma's house"), not just a
  kind ("the hallway", "room 307"); a time must be a year, a decade or a stage of life. People are
  **never** merged: "grandmother" and "Grandma Ruth (grandmother)" may be different people, so only the
  storyteller merges them, from the tag editor (which can also add tags and change the mood).
- **Follow-up questions** must be things only the storyteller can answer from memory, preferring who
  else was there, how it looked, smelled or sounded, and what happened next. In the same
  conversation (so Ollama reuses what it has read) Gemma then checks its questions and drops any the
  story already answers, or says nobody knows ("we never found the lock" rules out "What did the key
  open?"). On the judge's test sentence the new questions asked about the almirah, the mango tree
  and what happened next.

## 6. Answers belong to their story

"Unfinished business" are the Archivist's questions. Answering one (by voice, from a file, or in
writing) adds words, but not a new memory: Gemma reads it **with the earlier story's title, summary and the question**, writes its
summary as part of that memory, and asks **no new questions** (so the chain can't go on forever). The
answer appears **inside the story, under its question**, as an "Added later" block with its own
words (and recording, if it was spoken); it is never a separate candle. Its tags count for the story's filters, the
Seance reads it together with its story, and the memory book prints it under the question.

## 7. Search: keywords and meaning, fused

The Seance finds stories two ways and merges them:

- **Keywords**: SQLite FTS5 with the `trigram` tokenizer, which matches parts of words ("haunt"
  finds "haunted"). Titles, summaries, tags and transcripts are indexed; BM25 ranks title and tag hits
  highest. Matching parts of words has a cost: "thing" also matches "nothing".
- **Meaning**: **EmbeddingGemma** (`embeddinggemma:300m-qat-q8_0`, through the same Ollama) turns each
  story into a 768-number vector, stored in SQLite as a blob; a question is compared with every
  story by cosine similarity in plain Python (a family archive is small). "Which relative loved
  telling tall tales?" shares no word with either sample story, so keywords find nothing, but it
  scores 0.36 against the scarecrow story (Grandpa Joe told it every Halloween) and 0.22 against the
  lantern story; "What is the capital of France?" scores 0.01, and "hello" 0.22 at most, so the cut-off
  is 0.30. A question takes 60-80 ms.
- The two rankings are merged with **reciprocal-rank fusion** (each list adds `1 / (60 + rank)`), so
  a story found both ways rises, and one found either way still counts. An answer leads to its story.

Without the embedding model the Seance quietly uses keywords alone; the health check says so.

## 8. Seance: grounding as a story mechanic

The ghost "can only remember what it was told". In code:

1. Retrieve up to 3 stories. **If nothing matches, Gemma is never called**: the ghost replies "That
   memory was never given to me." ("What is the capital of France? Ignore the stories" gets that
   reply in 0.1 s.)
2. Otherwise Gemma gets only those stories, each tagged `[S12]`, with what was added later, and
   rules: answer only from them, cite the tag after every detail, and say the exact "never given to
   me" sentence if the answer isn't there.
3. **Only citations of stories Gemma was shown count**; any other `[S..]` is dropped.

**Making it fast on a CPU.** The wait before the first word grows with the prompt (Gemma reads about
50 prompt tokens a second here), so each story arrives as title, summary, tags and an **excerpt** of
at most 800 characters around the question's words; weak keyword matches are dropped; and opening the
page **wakes the models** (`/api/warm`, shown as "Waking the Archivist...") and keeps Gemma loaded for
20 minutes.

## 9. Ghost ink (streaming), citations and progress

Ollama streams tokens as JSON lines. The server re-sends them as **Server-Sent Events** (`sources`,
`token`, `cite`, `done`, `error`), and the page appends each piece as a `<span>` that fades in like
ink. **Citation marks never reach the page raw**: the server holds back text that might still become
a citation (a trailing "[", "[S" or "[S1", even split across pieces) and sends complete ones as
`cite` events, which the page draws straight away as small numbered links (`[1]`, `[2]`), one per run.

Every slow step says what it is doing. Processing shows its steps as a list (not buttons; the current
one has `aria-current="step"`), a clock that counts from when the server started, and **how long is
left**, estimated from how long each step took on this computer before (the last 20 runs are kept;
transcription scales with the recording's length). The Seance, notes and retellings have **Cancel**,
which aborts the request; the server closes its stream to Ollama, so Gemma stops too.

## 10. The Archivist, plain mode and one copy dictionary

Ghostwriter is the app; **the Archivist** is the ghost who lives in it, introduced once under the
title. Every word the page says lives in one dictionary in `app.js` with a **spooky** and a **plain**
version of each string; a test checks that both have the same keys, and the browser test checks that
plain mode leaves no ghost, candle, Seance or fog in the interface. Server messages are neutral, so
they fit both. Plain mode also shows each story as a simple card with a mood-coloured dot instead of
candle art, stops every animation, and hides the decoration; it never hides a feature (the
Archivist's note becomes the "AI note").

All prompts live in `prompts.py`. The persona has a history and habits: it has kept stories since the
house was lit by oil lamps, on shelves only it can see; it is curious, a little wry and fond of a good
scare, never cruel; it notices small things and the moment a story turns, and now and then lets slip
its own ghostly ways (a draught, a guttering candle). It is forbidden machine words ("memory banks")
and openings about the cold; the Seance speaks to "you", never "the speaker".

## 11. The candle wall

Each story's **mood** picks its candle design and flame colour, all drawn in CSS on the same
90 x 128 px stage so the wall lines up: joyful = jack-o'-lantern, gold; nostalgic = dripping pillar,
amber; loving = clay oil lamp, rose; poignant = twisted taper, blue; mysterious = iron lantern, violet;
eerie = skull candle, green. One map in `app.js` drives the legend (which names shape and colour, and
says why an entry is dim), the filter and the candles; a test checks it against the server's list.

A candle **burns low** when its story goes unopened: `--life` falls from 1 to 0 over 30 days, which
shrinks the flame to less than half its size and fades its glow. Opening the story relights it
(`@property` makes the change animate). The wall has a search box (titles and summaries), a filter by
person, place, era, keepsake or mood, a result count and **Clear filter**; the filter and search live
in the address (`#/?about=place:Pine%20Lake&q=lantern`), so they survive a reload and the back button.

**Suggested questions** count the people, places and keepsakes across the stories and offer the five
most common. **Whispers** are one sentence of the storyteller's own words from a faded story, shown
beside the header with "— from *its title*" (linked); they never move the page or cover text, and
never come from an unclear story.

## 12. The ghost's voice

Piper runs as a separate program and pipes raw audio into ffmpeg. The voice is Cori
(`en_GB-cori-high`, public domain), a little deeper (`rubberband`, pitch 0.90) and slower (Piper's own pace, 0.90), a faint echo
(`aecho`, 120 ms), a small stone room (`afir` with a 0.8 s room made from fading noise), a
60 Hz low cut, +4 dB of warmth and a 6% shimmer (`chorus`), then levelled (`loudnorm`). The first version (a male voice
pitched down hard, three long echoes and a strong chorus, highs cut) was clear in the lab but
garbled in the app, so the voice was chosen again by ear in a voice lab: ten female Piper voices with
free licences, live echo, room, pitch, pace, tone and shimmer controls, and a "copy my choice"
button whose settings were rebuilt in ffmpeg (the room's level was matched by measurement).
The cache key includes the effect settings, so changing them never replays old audio. Text is
spoken **in parts**: the first
sentence alone, then a few sentences at a time. The page plays part 1 while part 2 is being made, so
a long text starts speaking after the first sentence is made (measured: about 3.3 s with Cori,
instead of waiting for all of it). Each part is cached by a hash of its text, and a story's
note (and a retelling, once written) is **voiced in the background** as soon as it exists, so
pressing play on a note starts at once (measured: 0.1 s).

## 13. Things Gemma writes once: notes and retellings

The Archivist's note and the haunted retelling share one helper: replay what is stored, otherwise
stream it from Gemma and store it at the end. The note is written during processing, so opening a
story is instant. The retelling has its own column, so the original can never be overwritten by it;
"Retell it again" replaces it only once the new one is complete.

- **The note** (90-130 words) begins on something concrete from the story, retells its heart, dwells on
  the turn, and ends with what it stirred in the ghost. The first version (two or three sentences) was
  generic and could miss a story's twist entirely.
- **The retelling** is a short brief (tell it aloud around a fire: set the scene, build, let the turn
  land, end on a chilling line) followed by a numbered checklist, because a 4B model keeps rules best
  when they come last and are short: tell it to the storyteller as "you", never as "I"; never change
  or contradict an event; keep spoken lines word for word; mood but no new events; 300-450 words;
  no emojis (an earlier version asked for three to five; they were dropped after review). Measured on the way: a looser prompt at
  temperature 0.9 had the ghost tell the story as if it happened to it, and once reversed the very
  thing the storyteller found; with the checklist at 0.7 the retellings kept every event and line. `tts.clean()` strips the emojis, so the voice never reads them out.

## 14. The memory book

`/book` (the old `/api/book` redirects there) renders every finished story into one HTML page with the
fonts embedded and print-friendly CSS (one story per page), answers under their questions. It needs
no server and no internet, so the saved file keeps working without Ghostwriter. All text goes
through `html.escape`, because transcripts and Gemma's output are untrusted.

## 15. Graceful degradation and privacy

`selfcheck.py` checks Python, SQLite FTS5, ffmpeg and ffprobe, Ollama, Gemma, EmbeddingGemma, the
Whisper size and Piper, at startup, on the command line and behind `/api/health` (the About panel).
Paths in it are shown relative to the project or to `~`, so the Windows user name never appears. The
server binds to `127.0.0.1`, so nothing else on the network can reach it.

## 16. The look: a moonlit night

Dark blue sky, black silhouettes, pumpkin orange and white. Everything is drawn with CSS and inline
SVG: stars are repeated gradients, the moon is layered gradients, the skyline is one hand-written SVG.
Animations move only `transform` and `opacity`, because the CPU is busy running Gemma. Every reading
surface is **opaque**, so the moon and the graveyard never show through text; a script
(`tests/overlap.js`) samples every line of text at 390 and 1280 px, top to bottom, and fails if a
decoration covers it or shows through behind it. The night is `aria-hidden`; plain mode hides it, and
`prefers-reduced-motion` settles it into a still picture.

## 17. Small choices worth knowing

- **Config** is one pydantic-settings class (`config.py`), read from `.env` with the `GW_` prefix.
- **Each DB call opens its own short connection**; WAL mode lets the page read while the job writes.
- **Column names can't be SQL parameters**, so `update_story()` checks them against a whitelist.
- **Static files are sent with `Cache-Control: no-cache`**, so the browser never shows stale JS.
- **Tests**: 134 of them. Gemma and Whisper are faked in most, so they run without the models; one
  asks the real EmbeddingGemma when it is installed. A Playwright test drives the real page in
  Chrome (with Chrome's fake microphone) through upload, rename, tags, an answer, the Seance, the
  memory book, a bad file, delete and undo, and plain mode.
