# How Ghostwriter works

Plain-language notes on the main design decisions, for the write-up and for interviews.
Each section is: what it does, how, and why this way.

## 1. The big picture

You give the ghost a recording. A background job turns it into a stored, searchable story:

```
original audio --ffmpeg--> 16 kHz mono WAV --Whisper--> transcript --Gemma--> title, summary,
people, places, eras, mood, keepsakes, follow-up questions --> SQLite (+ full-text index)
```

Then you can ask the archive questions (Seance), and the Archivist answers only from your stories,
written out live in a handwriting font.

Everything runs on the laptop. The web page talks only to `127.0.0.1`; the server talks only to
Ollama on `127.0.0.1:11434`; Whisper loads its weights from a folder on disk.

## 2. Why process after recording, not live?

Live transcription on a CPU-only laptop would be choppy and would compete with Gemma for the CPU.
Processing after the recording finishes is simpler, more accurate (Whisper sees the whole clip),
and fast enough: about 35 s of work per minute of audio with Whisper `small` on an i7-13620H.

## 3. Never losing a story

- The original upload is saved **untouched** before anything else happens. The stored filename comes
  from the story's id, never from the uploaded name, so a crafted filename can't write elsewhere.
- Each pipeline step **saves its result before the next step starts** (WAV, then transcript, then
  analysis). If Gemma is down, the transcript is already safe.
- A failed story keeps its error message and gets a **Try again** button. A retry skips the steps
  that already succeeded.
- If the app is killed mid-job, the next start marks that story "interrupted" so it can be retried,
  instead of leaving it stuck forever.
- Jobs run **one at a time** (a lock), so Whisper and Gemma never fight over 16 GB of RAM.

## 4. Getting reliable JSON out of a small model

Gemma must return title, summary, people, places, eras, mood, keepsakes and 2-4 questions.
Three layers make that reliable:

1. **Ollama structured output**: the JSON schema (generated from a pydantic model) is sent as the
   `format`, so the model's sampling is constrained to valid JSON of that shape.
2. **Strict validation**: the reply is parsed by the same pydantic model (`StoryAnalysis`), which
   also checks rules the schema hints at, such as "2 to 4 questions" and "no empty title".
3. **One repair attempt**: if validation fails, Gemma is shown its own reply plus the exact error and
   asked to fix it, once. If that fails too, the story is marked failed (transcript kept) rather than
   storing half-broken data.

## 5. Search: SQLite FTS5 with the trigram tokenizer

Stories are indexed with SQLite's built-in full-text search (FTS5). The `trigram` tokenizer splits
text into 3-character pieces, which means:

- it works the same for **Devanagari and Latin script**, with no language-specific rules;
- it matches **substrings**, so "haunt" finds "haunted" (a cheap kind of stemming).

Triggers keep the index in step with the `stories` table automatically. Results are ranked by
**BM25**, weighting title hits 3x and summary hits 2x over transcript hits.

Gemma writes titles and summaries **in English** even for Hindi stories. That gives an English
question something to match even when the transcript is in Devanagari. The people, places, eras and
keepsakes Gemma extracts are also indexed, as a `tags` column. Without that, "What did Nani cook?"
found nothing: the transcript said नानी and the summary said "grandmother". When the indexed columns
change, `init_db()` drops and rebuilds the index (it only mirrors the table, so nothing is lost).

## 6. Seance: grounding as a story mechanic

The ghost "can only remember what it was told". In code:

1. Retrieve up to 3 stories with FTS5. **If nothing matches, Gemma is never called**: the ghost
   replies "That memory was never given to me." There is nothing it could honestly say.
2. Otherwise Gemma gets only those stories, each tagged `[S12]`, with rules: answer only from them,
   cite the tag after every detail, and say the exact "never given to me" sentence if the answer
   isn't there.
3. After streaming, the server keeps **only citations of stories Gemma was actually shown**. The page
   turns those into links to the story; any other `[S..]` tag is dropped.

**Making it fast on a CPU.** Measured, the wait before the first word grows with the prompt: Gemma
reads about 50 prompt tokens a second here (~560 tokens: 8-13 s; ~1,090 tokens: 17-23 s). Using 6
threads instead of Ollama's 8 made no difference. So the Seance sends less:
- each story arrives as title, summary, tags and an **excerpt**: only the transcript sentences that
  mention the question's words, plus their neighbours, at most 800 characters (`prompts.excerpt`);
- a match that scores **under half the best match** is dropped (`search.RELEVANCE`);
- opening the page **loads Gemma in the background** (`/api/warm`), and every request asks Ollama to
  keep it loaded for 20 minutes, so a question never waits ~20 s for the model to load.

On stories five times the length of the samples this cut the prompt from ~1,050 to ~670 tokens and
the first word from 17-23 s to 10-14 s. On the short samples it changes little (they were already small).

## 7. Ghost handwriting (streaming)

Ollama streams tokens as JSON lines. The server re-sends them to the browser as **Server-Sent
Events** (`sources`, `token`, `done`, `error`). The page reads the stream with `fetch` and appends
each piece as a `<span>` that fades in from a blur (CSS animation) in the Caveat handwriting font,
while the whole passage flickers faintly like candlelight. `prefers-reduced-motion` and plain mode
turn the effects off.

## 8. The Archivist and plain mode

All prompts live in `prompts.py`, so the voice is consistent and easy to tune. The persona is a
system prompt (old-fashioned, gently dramatic, warm, never cruel). **Plain mode** swaps it for a
neutral one and switches the page's wording and fonts. Follow-up questions are stored neutrally, and
the Archivist's voice is applied only when they're presented, so plain mode stays plain.

Two persona bugs taught the most. The Seance kept saying "the speaker" because Gemma copied the
third-person summaries it was shown, so summaries are now written to "you". And once the ghost
mentioned its "memory banks", so the persona now forbids machine words.

## 9. The candle wall and whispers

A candle's life is `1 - days_since_visit / 30`, never below 0.12, passed to CSS as a custom
property `--life`. It dims the flame only gently (never below about 70% of full size and brightness),
so the wall stays even. Registering it with `@property` makes it animatable, so opening a story (which
records the visit) lets the flame grow back smoothly.

Each story's **mood** picks its candle. Gemma must choose one of six moods (a `Literal` in
`models.py`, so Ollama's structured output can only produce those words), and each has its own
design and flame colour, all drawn in CSS on the same 90 x 128 px stage so the wall lines up:
nostalgic = dripping pillar, amber; poignant = twisted taper in a brass candlestick, blue;
mysterious = candle in an iron lantern, violet; eerie = skull candle, green; joyful = jack-o'-lantern,
gold; loving = clay diya, rose. Shape and colour together mean colour is never the only cue. A key
under the wall names the colours, and each entry is a button: it lights only that mood's candles
(it sets the same filter as the menu, so the two always agree; moods with no stories are greyed out).
Stories analysed before the moods were fixed get the pillar.

The Seance's **suggested questions** need no model either: the page counts the people, places and
keepsakes across all finished stories and offers the five most common ("Ask about Jaipur"). On a tie,
real names beat relations like "father", and near-duplicates ("grandfather", "grandfather's father")
are skipped. A click asks "Tell me about Jaipur.", whose only search word is the name.
Whispers need no model: they are one sentence of the storyteller's own words, picked from the three
least recently visited stories, which nudges you back toward what you've forgotten.

## 10. The ghost's voice

Piper (open-source neural text-to-speech) runs as a separate program and writes raw audio to its
standard output, which is piped straight into ffmpeg: `rubberband` lowers the pitch without changing
the speed, `lowpass` softens it, a three-tap `aecho` makes a stone room, and `chorus` adds a faint
doubling. No temporary files (Piper couldn't write to a very long path). The WAV is cached by a hash
of the text, so a line is only ever made once. Citation marks are removed before speaking.

## 11. Things Gemma writes once: reactions and retellings

The Archivist's reaction to a story and the haunted retelling share one helper: if the text is
already stored, replay it; otherwise stream it from Gemma and store it at the end. The retelling has
its own column, so the original transcript and summary can never be overwritten by it (a test checks).

## 12. The memory book

`/api/book` renders every finished story into one HTML page with the fonts embedded as base64 and
print-friendly CSS (one story per page). It needs no server and no internet, so the saved file keeps
working even if Ghostwriter doesn't. All text goes through `html.escape`, because transcripts and
Gemma's output are untrusted.

## 13. Graceful degradation

`selfcheck.py` checks Python, SQLite FTS5, ffmpeg, Ollama, the Gemma model, Whisper weights and
Piper. The same checks run at startup, on the command line and behind `/api/health`, and the page
shows a banner with a plain fix for anything required that's missing ("Run: ollama pull gemma4:e4b").
Errors from Ollama are translated into actionable messages instead of stack traces.

## 14. The look: a moonlit night

Dark blue sky, black silhouettes, pumpkin orange and white, inspired by how Halloween shops and
sites dress their pages (smoky orange glows, moonlit skies, bats, fog, haunted houses). Everything is
drawn with CSS and inline SVG, so there are no image files and nothing to download: the stars are
repeated radial gradients, the moon is layered gradients, the skyline is one hand-written SVG, the bats
are one SVG symbol reused three times. The animations move only `transform` and `opacity`, which the
browser can hand to the graphics chip, because the CPU is busy running Gemma.

Two small touches use modern CSS instead of JavaScript: the crystal ball swirls faster while the
Seance button is disabled or the ghost is writing (`#seance:has(.writing)`), and the retelling's
campfire glow is attached with `section:has(> .retelling)`. The only new JavaScript moves the
visitor's lantern glow and makes the ghost say "Boo!" when poked.

The night is decoration only (`aria-hidden`). Plain mode hides it, and `prefers-reduced-motion`
settles every animation into its final, still state.

## 15. Small choices worth knowing

- **Config** lives in one pydantic-settings class (`config.py`), read from `.env` with the `GW_`
  prefix. Relative paths are resolved against the project folder, not the current directory.
- **Each DB call opens its own short connection.** SQLite is fast to open, and this avoids sharing
  a connection between FastAPI's threads. WAL mode lets the page read while the job writes.
- **Column names can't be SQL parameters**, so `update_story()` checks them against a whitelist.
- **Static files are sent with `Cache-Control: no-cache`**, so the browser never shows stale JS
  after an update.
- **Tests never need the models**: Gemma and Whisper are replaced with fakes, and every test gets
  its own temporary data folder.
