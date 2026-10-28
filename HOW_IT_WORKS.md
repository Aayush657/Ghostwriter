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
question something to match even when the transcript is in Devanagari.

## 6. Seance: grounding as a story mechanic

The ghost "can only remember what it was told". In code:

1. Retrieve up to 3 stories with FTS5. **If nothing matches, Gemma is never called**: the ghost
   replies "That memory was never given to me." There is nothing it could honestly say.
2. Otherwise Gemma gets only those stories, each tagged `[S12]`, with rules: answer only from them,
   cite the tag after every detail, and say the exact "never given to me" sentence if the answer
   isn't there.
3. After streaming, the server keeps **only citations of stories Gemma was actually shown**. The page
   turns those into links to the story; any other `[S..]` tag is dropped.

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

## 9. Graceful degradation

`selfcheck.py` checks Python, SQLite FTS5, ffmpeg, Ollama, the Gemma model, Whisper weights and
Piper. The same checks run at startup, on the command line and behind `/api/health`, and the page
shows a banner with a plain fix for anything required that's missing ("Run: ollama pull gemma4:e4b").
Errors from Ollama are translated into actionable messages instead of stack traces.

## 10. Small choices worth knowing

- **Config** lives in one pydantic-settings class (`config.py`), read from `.env` with the `GW_`
  prefix. Relative paths are resolved against the project folder, not the current directory.
- **Each DB call opens its own short connection.** SQLite is fast to open, and this avoids sharing
  a connection between FastAPI's threads. WAL mode lets the page read while the job writes.
- **Column names can't be SQL parameters**, so `update_story()` checks them against a whitelist.
- **Static files are sent with `Cache-Control: no-cache`**, so the browser never shows stale JS
  after an update.
- **Tests never need the models**: Gemma and Whisper are replaced with fakes, and every test gets
  its own temporary data folder.
