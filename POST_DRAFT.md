---
title: I Built a Ghost That Lives in My Laptop and Keeps My Family's Stories
published: false
tags: devchallenge, hf26challenge
---

*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 4: Ghost in the Machine](https://dev.to/challenges/hacktoberfest-week4-2026-10-26)*

## What I Built

In most families I know, the best stories have never been written down. They live in one person's
voice: a grandparent after dinner, an uncle at a wedding, the friend who tells the hostel ghost story
better than anyone. When that voice goes quiet, the stories go with it.

[PLACEHOLDER: one or two true sentences about whose stories made you want to build this.]

So I built **Ghostwriter**, the ghost that keeps your stories.

A ghost lives in your laptop. It calls itself **the Archivist**. You tell it a story out loud, in
Hindi, English, or the mix most of us actually speak, and it:

- **writes it down**, word for word, and keeps your original recording;
- **understands it**: gives it a title and a short summary, and notes who was there, where, when,
  and the objects, recipes and sayings worth keeping;
- **notices what you left out**, and asks: *"You never told me where the brass pot went..."* Answer
  out loud, and your answer is kept beside the story it completes;
- **holds a séance**: ask your archive anything, and the ghost answers only from what you told it,
  citing the story it remembered;
- **lights a candle for every story** on a wall strung with orange and white lights. The story's mood
  picks the candle: a skull with a green flame for the eerie ones, a jack-o'-lantern for the joyful,
  a clay diya for the loving. Stories you haven't visited in a while burn lower. Open one, and its
  flame comes back;
- **speaks** in a low, echoing voice, and on request **retells** any memory as a campfire
  bhoot-kahani (always labelled as a retelling; the original is never touched).

The rule that makes it work is a story mechanic as much as a technical one: **the ghost can only
remember what it was given.** Ask it about something you never told it, and instead of inventing an
answer it says:

> *"That memory was never given to me."*

It is spooky on the surface and sentimental underneath. And all of it runs on my laptop, with open
models, with the Wi-Fi switched off.

## Demo

[PLACEHOLDER: demo video embed, e.g. `{% embed https://www.youtube.com/watch?v=VIDEO_ID %}`]

In the video I switch the Wi-Fi off in a dark room, tell the ghost a story, and let it write.

[PLACEHOLDER: screenshot: the candle wall]

[PLACEHOLDER: screenshot: a séance answer in the ghost's handwriting, with its story linked]

[PLACEHOLDER: screenshot: a story page with "Unfinished business"]

**The moment that made it worth it:** [PLACEHOLDER: what happened when someone heard their own story
read back by the ghost. Describe only what really happened. If you didn't get to do this, delete this
paragraph.]

Project page: [PLACEHOLDER: your .tech link]

## Code

[PLACEHOLDER: `{% github YOUR_USERNAME/ghostwriter %}`]

MIT licensed. The README has one-command setup for Windows, and the repo includes four clearly
fictional sample stories, so you can try the ghost without recording anything.

## How I Built It

### The pipeline

```
 Browser (plain HTML/CSS/JS from 127.0.0.1, fonts bundled)
   |  record / upload                     ^  Server-Sent Events: tokens become "ghost handwriting"
   v                                      |
 FastAPI ----------------------------------+
   |-- ffmpeg          any recording -> 16 kHz mono WAV (the original is kept)
   |-- faster-whisper  Whisper small, int8, on the CPU; language auto-detected
   |-- Ollama          Gemma 4 e4b: structured JSON, then streamed answers
   |-- SQLite          stories, people, places, questions + an FTS5 full-text index
   '-- Piper + ffmpeg  the Archivist's voice
```

Everything is Python 3.11 with FastAPI, and a frontend of plain HTML, CSS and JavaScript with no
build step. There is no React and no CDN, because a page that loads a font from Google Fonts isn't
offline.

Recordings are processed **after** they finish, not live, one job at a time. On a CPU-only laptop
that's both faster and kinder to 16 GB of RAM, since Whisper and Gemma never compete. Each step saves
its result before the next starts, so if Gemma isn't running, the transcript is already safe and a
**Try again** button picks up where it stopped.

### Getting reliable JSON out of a small model

For every story, Gemma has to return a title, summary, people, places, eras, mood, keepsakes and two
to four follow-up questions. A 4B-class model will occasionally return something that isn't quite
that, so there are three layers:

1. Ollama's structured outputs: I pass the JSON schema of a pydantic model as `format`, which
   constrains generation to that shape.
2. The same pydantic model validates the reply, including rules like "two to four questions".
3. If validation fails, Gemma sees its own reply plus the exact error and gets **one** chance to repair
   it. If that fails too, the story is marked failed with its transcript kept, rather than stored
   half-broken.

It handled Hindi better than I expected. From a Devanagari transcript it wrote an English summary,
listed "Nani (grandmother)" and "Mama (uncle)", and turned *अस्सी के दशक* into "1980s".

### Grounding as a story mechanic

The séance is retrieval-augmented generation with a costume on:

1. **Search.** SQLite's built-in FTS5 index with the `trigram` tokenizer, which works the same on
   Devanagari and English and matches parts of words ("haunt" finds "haunted"). Results are ranked
   with BM25, with titles and tags weighted above the transcript.
2. **No match, no Gemma.** If nothing matches, the model is never called. The ghost simply says the
   memory was never given to it. There is nothing it could honestly say, so it doesn't get the chance.
3. **Answer only from the stories.** Gemma gets the retrieved stories, each tagged like `[S12]`, and
   must cite a tag after every detail. After streaming, the server keeps only citations of stories
   Gemma was actually shown, and the page turns those into links.

I tried to make it lie. Asked *"Was it my grandfather's ghost who made the tea?"*, when no grandfather
appears anywhere in the story, it refused. Asked *"Did my great-grandfather ever come home from
Rangoon?"*, it answered with the story's own ending: nobody in the family knows.

### Ghost handwriting, candles and a voice

Ollama streams tokens; FastAPI passes them on as Server-Sent Events; the browser adds each piece as a
span that fades in from a blur, in the Caveat handwriting font, while the paragraph flickers faintly
like candlelight. It turns the wait for a CPU-bound model into part of the séance.

Each candle's brightness is just `1 - days_since_visit / 30`, with a floor so it never quite goes out.
A registered CSS custom property (`@property --life`) lets the flame grow back smoothly when you open
the story.

The voice is Piper, an open-source neural text-to-speech engine, piped straight into ffmpeg:
`rubberband` lowers the pitch without slowing the speech, then a three-tap `aecho` makes a stone
room and a little `chorus` adds the ghostly doubling. Eleven seconds of speech take 1.2 seconds to
make.

### Things that went wrong (and taught me something)

- **"The speaker."** The séance kept saying "the speaker heard humming" instead of "you heard
  humming". The cause wasn't the séance prompt. It was my own summaries, which Gemma had written in
  the third person and was now copying. Writing the summaries in the second person fixed both.
- **"Memory banks."** Asked to react to a story, the 19th-century ghost mentioned its *memory banks*.
  One line in the persona now forbids machine words. Its next try: *"A chill brushes my spectral
  form."*
- **Hindi names.** "What did Nani cook?" found nothing, because the transcript said नानी, the summary
  said "grandmother", and "Nani" only existed in a table the search index didn't cover. I added the
  extracted names, places and objects to the index as tags (with a migration that rebuilds older
  databases).
- **Downloads.** winget's downloader failed on my connection, Hugging Face's newer transfer protocol
  stalled at 0 bytes, and the 6.6 GB Gemma download kept stalling on individual chunks. I fell back
  to `curl` with SHA256 checks against winget's own manifests, and to plain HTTPS for Hugging Face.

### Real numbers

Measured on my laptop: Intel i7-13620H, 16 GB RAM, integrated graphics only, so everything runs on
the CPU.

| What | Result |
|---|---|
| Whisper small (int8), English test clip | about 35 s per minute of audio |
| Whisper on my own Hindi/Hinglish recording | [PLACEHOLDER: measure on your recording] |
| Gemma 4 e4b generation | 11-14 tokens per second |
| Gemma cold start | 15.8 s |
| Understanding one story (JSON) | 27-36 s |
| Séance answer | first words in 7-19 s, complete in 11-26 s |
| Same question context, asked again | first word in 0.7 s (Ollama's prompt cache) |
| Ghost voice | 11.2 s of speech in 1.2 s |

### What isn't great yet

- It's slow on a CPU. Streaming makes a 10-second wait feel atmospheric, but it's still a wait.
- Search matches words, not meanings: "dessert" won't find a story that only says "kheer".
- Whisper `small` mishears names (my test clip turned "Shimla" into "Chimla"); `medium` is better and
  slower.
- Gemma's follow-up questions are occasionally a little off.
- The ghost answers and speaks in English, even about Hindi stories.
- It's Windows-first and single-user.

### Built with AI assistance

I built Ghostwriter with Claude Code as a pair programmer. [PLACEHOLDER: describe honestly how you
split the work, e.g. which product decisions, testing and writing were yours.] Every number in this
post was measured on my machine during the build; the logs are in `PROGRESS.md` in the repo.

## Why Does Open Innovation Matter?

Because this project would be a bad idea in the cloud.

- **Voices never leave the laptop.** These are recordings of family members, sometimes people who
  are no longer here. I don't want a grandmother's voice to be someone's training data, or to depend
  on a privacy policy I didn't write. Here the recordings, transcripts and stories are a folder and a
  SQLite file on my own disk.
- **It works with the lights and the internet off.** I recorded the demo with the Wi-Fi switched
  off. Fonts, scripts and models are all local, and every request the page makes goes to `127.0.0.1`.
- **There's no API bill.** I'm a student. Every transcription, every séance question and every
  retelling costs me nothing but electricity, so I can ask the ghost as many questions as I like.
- **The archive outlives any company.** If Ghostwriter stopped existing tomorrow, the stories
  wouldn't. "Open the memory book" exports everything as one self-contained HTML file, fonts included,
  that any browser can open years from now.
- **I can swap the brains.** The models are one line each in a settings file. An older laptop can
  run `gemma4:e2b`; better Hindi transcription is one word away (`medium`). When a better open model
  ships, I change a line instead of a contract.

The open approach was harder in specific ways, and I'd rather say so:

- **Setup is heavier.** The models add up to over 7 GB. On my connection, Gemma alone took about 35
  minutes, with stalled chunks and a failing installer along the way. A hosted API would have been
  one key.
- **Small local models need guard rails.** Structured outputs, validation, one repair attempt, and
  a persona that has to be told not to sound like a machine. The upside is that I can see and test
  every guard rail.
- **CPU speed shapes the design.** Processing after recording, one job at a time, streaming
  everything, and caching the voice all exist because there's no GPU doing the work.
- **Licences matter more when you ship the weights.** I chose the ghost's voice by its licence:
  two other candidate voices were licensed for non-commercial use only, so I used one trained on a
  CC BY-SA dataset. Piper (which bundles the GPL-licensed espeak-ng) runs as a separate program, and
  everything is credited below.
- **"Offline" needs an asterisk.** Ollama itself asks ollama.com for model recommendations when it's
  online. Ghostwriter never does, and nothing breaks without the network, but I'd rather you heard
  it from me.

## The Spirit of It

Día de los Muertos isn't about being scared of the dead. It's about keeping them close: an ofrenda,
candles, marigolds, their favourite food, their stories told again. Ghostwriter tries to be a small
digital ofrenda. The ghost isn't there to frighten anyone. It's there to keep the people we tell
stories about from fading, and the candle wall shows that literally: a memory dims when nobody
visits it, and comes back when someone does.

## Prize Categories

- **Best Use of Gemma:** Gemma 4 e4b, running locally through Ollama, does all the understanding:
  structured extraction from Hindi and English transcripts, grounded séance answers with citations,
  the Archivist's voice, and the haunted retellings.
- **Best Use of a .tech Domain:** the project page lives at [PLACEHOLDER: your .tech domain].

## My Agent Session

[PLACEHOLDER: DevRelay link, or delete this section.]

## Credits

Gemma 4 by Google DeepMind (Apache 2.0) · Ollama (MIT) · Whisper by OpenAI, via faster-whisper and
CTranslate2 (MIT) · Silero VAD (MIT) · Piper by Rhasspy (MIT) with espeak-ng (GPL-3.0) and ONNX Runtime
(MIT) · the `en_GB-northern_english_male-medium` voice, trained on OpenSLR 83 (CC BY-SA 4.0) · FFmpeg
(GPL-3.0) · SQLite (public domain) · FastAPI, Uvicorn, httpx, pydantic · Caveat and IM Fell English
fonts (SIL Open Font License). The sample stories in the repo are fictional and written for this
project. Full details are in the README.

If you build your own, tell it something true. It's listening.

<!-- ======================= NOT PART OF THE POST: notes for you ======================= -->
<!--
Before publishing:
1. Search this file for "PLACEHOLDER" and fill or delete every one. Never invent the "real moment".
   The post says the demo was recorded with the Wi-Fi off: keep that only if the video shows it.
2. The front matter must stay the very first thing in the post. DEV allows up to 4 tags; the two
   required ones are there. You may add e.g. "ai" and "opensource".
3. Re-read it aloud once in your own voice and change anything that doesn't sound like you.
4. Delete this comment block before publishing.
5. Prize Categories: keep both only if the .tech page is actually live.
-->
