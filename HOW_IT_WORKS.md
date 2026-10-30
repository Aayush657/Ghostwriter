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

## 2. Hearing the words right

Memory accuracy is the whole product, so most of the work goes into the transcript.

- **The storyteller chooses the language** next to the record button: detect it, English, Hindi, or
  Hinglish. The choice is remembered, shown on the story ("Hindi (you chose it)" or "English
  (auto-detected)"), and can be changed later with **Listen again in...**, which transcribes the same
  recording again and re-reads it. Hinglish is Whisper's Hindi mode plus an example sentence that
  keeps English words in Latin script ("मैं school से आता था"); measured, that is what makes Whisper
  write "school" instead of "सकूल".
- **A glossary guides Whisper.** Before listening, Whisper reads a short prompt: the people, places
  and keepsakes already in the archive (most mentioned first), then common Indian family words and
  cities (Nani, Dadi, almirah, kadhi, Pune, Lucknow...). On a clear test clip this turned "Mira",
  "Puna" and "armourer" into "Meera", "Pune" and "almirah". A name the archive has never heard can
  still be misheard; correct it once in the tag editor and later recordings get it right.
- **Beam search, voice detection and word probabilities.** `beam_size=5`, Silero VAD to skip silence
  (fewer invented words), and `word_timestamps=True`, which gives every word its own probability.
  Words Whisper gave less than even odds are listed under the transcript ("The Archivist wasn't sure
  of these words: ..."), so you know what to check.
- **The model size is a setting** (`GW_WHISPER_MODEL`: `small`, `medium`, `large-v3-turbo`...); the
  health check shows which sizes are downloaded. README > Whisper size has the trade-off.

## 3. The quality gate: fog is not a memory

A noisy recording once came back as a mix of Urdu, Chinese and Latin letters, and Gemma dutifully
made it a "memory" ("Unclear Memory Fragment: The transcript provided contains fragmented..."). Now,
between Whisper and Gemma, `transcribe.judge()` looks at Whisper's own confidence:

- average log-probability below -0.8: Whisper was guessing;
- compression ratio above 2.4: a repetition loop (Whisper's own threshold);
- three or more alphabets in the text;
- or two weak signs together: log-probability below -0.55, more than 20% unsure words, a detected
  language with under 60% certainty, or a high no-speech probability.

The thresholds come from real recordings: clear speech scores about -0.3 with almost no unsure words;
the noisy room recording scored -0.67 with 29% unsure words and failed all four weak signs; English
speech forced into Hindi scored -1.70. A story that fails gets the status **unclear**: no title,
summary or questions are invented, it stays out of the Seance, the memory book and the whispers, and
its page says *"The words came to me as fog..."* with three ways forward: listen again in another
language, correct the words by hand (a person's words skip the check), or delete it.

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

- **Keywords**: SQLite FTS5 with the `trigram` tokenizer, which works the same for Devanagari and
  Latin script and matches substrings ("haunt" finds "haunted"). Titles, summaries, tags and
  transcripts are indexed (tags let "Nani" find a story whose transcript says नानी); BM25 ranks title
  and tag hits highest.
- **Meaning**: **EmbeddingGemma** (`embeddinggemma:300m-qat-q8_0`, through the same Ollama) turns each
  story into a 768-number vector, stored in SQLite as a blob; a question is compared with every
  story by cosine similarity in plain Python (a family archive is small). "Which of my relatives was
  a good cook?" shares no word with "Grandmother's Famous Kadhi in Lucknow", but scores 0.36 against
  it; unrelated questions ("the capital of France", "hello") score 0.17 at most, so the cut-off is 0.30.
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

All prompts live in `prompts.py`. The persona is warm, old-fashioned and never cruel, and is forbidden
machine words ("memory banks"); the Seance speaks to "you", never "the speaker".

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

Piper runs as a separate program and pipes raw audio into ffmpeg (`rubberband` lowers the pitch,
`aecho` makes a stone room, `chorus` adds a faint doubling). Text is spoken **in parts**: the first
sentence alone, then a few sentences at a time. The page plays part 1 while part 2 is being made, so
a long text starts speaking after the first sentence is made (measured: 2.3 s for a new six-sentence
retelling, instead of waiting for all of it). Each part is cached by a hash of its text, and a story's
note (and a retelling, once written) is **voiced in the background** as soon as it exists, so
pressing play on a note starts at once (measured: 0.1 s).

## 13. Things Gemma writes once: notes and retellings

The Archivist's note and the haunted retelling share one helper: replay what is stored, otherwise
stream it from Gemma and store it at the end. The note is written during processing, so opening a
story is instant. The retelling has its own column, so the original can never be overwritten by it;
"Retell it again" replaces it only once the new one is complete. The retelling prompt asks for a few
emojis (about one every two or three sentences, at the end of a sentence, never in place of a word),
which makes it livelier to read; `tts.clean()` strips them, so the voice never reads them out.

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
