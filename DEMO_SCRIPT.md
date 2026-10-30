# Ghostwriter: demo video script (2:00, with a 1:30 cut)

**The one rule:** every shot is real. The only cut is the processing wait, and the video says so on
screen. Don't speed anything up without a caption.

## Before you record

- [ ] Models already downloaded (`selfcheck` all green, including "Meaning search"). Nothing can be
      fetched once Wi-Fi is off.
- [ ] Start the archive you'll show: `scripts\demo.ps1` (the fictional samples) or `scripts\run.ps1`
      (your real stories), from the project folder. Using the demo archive? Say on screen that the
      samples are fictional.
- [ ] Open http://127.0.0.1:8000 in Chrome a minute before recording: the page wakes the models
      ("Waking the Archivist..." then "The Archivist is awake."), so nothing waits ~20 s on camera.
- [ ] Practise the Seance questions once, so the stories they need exist and the answers are good.
      A new recording always gives a fresh "The Archivist writes" note.
- [ ] Browser: full screen (F11), zoom 110-125% so the text is readable on a phone.
- [ ] Screen recorder: OBS Studio (open source, fits the theme) or Windows' Snipping Tool video.
      **Capture system audio**, or the ghost's voice won't be in the video.
- [ ] Room: lights off, one real candle or a jack-o'-lantern beside the laptop if you have one. A phone on a
      stand for the room shots. Record your story somewhere quiet, close to the microphone.
- [ ] Optional but worth everything: someone in your family, ready for the last shot (ask first).

## The script

| Time | Shot | What happens on screen | Voice-over (yours) / caption |
|---|---|---|---|
| 0:00-0:08 | **Room, phone camera.** Dark room, laptop glowing, a candle beside it. | The candle wall on screen. | VO: "The best stories in my family were never written down. So I built a ghost to keep them." |
| 0:08-0:18 | **Close-up of the taskbar**, then the terminal. | Turn Wi-Fi off (or airplane mode) on camera. Run `.venv\Scripts\python.exe -m ghostwriter.selfcheck`: all green. | Caption: **Wi-Fi: off.** VO: "Everything you're about to see runs on this laptop. No internet, no cloud, no API key." |
| 0:18-0:28 | **Screen.** Candle wall. | Hover a low-burning candle (the scarecrow sample: "Not opened for 20 days"). | VO: "Every candle is a story. The ones I haven't opened are burning low." |
| 0:28-0:42 | **Screen.** "Give the Archivist a story". | Click *Record a story* (English); the clock and level meter run. Tell a 10-15 second story. Click *Stop and keep it*. The steps appear: Listening, Reading, Writing the note, with the time left. | Caption on the cut: **"About a minute later. Whisper and Gemma, both on the CPU."** |
| 0:42-1:02 | **Screen.** The new story's page. | Title and summary of what you said. *The Archivist writes* is already there. Scroll to *Unfinished business*. | VO: "Whisper wrote it down, Gemma understood it, and asked about the part I skipped." |
| 1:02-1:22 | **Screen.** Seance. | Ask something your stories answer in other words (e.g. "Which of my relatives was a good cook?"): the answer writes itself in, with a numbered source. Then ask something you never told it: *"That memory was never given to me."* | VO: "It finds stories by meaning, and only answers from what I told it. When it doesn't know, it says so." |
| 1:22-1:36 | **Screen.** | Click *Let the Archivist speak*: the ghost voice plays at once. Optional: *Retell it as a ghost story*, first lines. | (Let the voice speak. No VO.) |
| 1:36-1:50 | **Room, phone camera.** | **The real moment:** someone hearing their own story read back by the ghost. | [PLACEHOLDER: what actually happened. Don't stage it; if it doesn't happen, cut this shot.] |
| 1:50-2:00 | **End card.** | "Ghostwriter: the ghost that keeps your stories. Gemma 4, EmbeddingGemma, Whisper, Piper. Fully offline." github.com/Aayush657/Ghostwriter and theghostwriter.tech. | VO: "Tell it something true. It's listening." |

Optional, if you have 10 more seconds: open the *Words lost in fog* candle (an unclear recording) to
show that the ghost refuses to make a memory out of noise, and that you can write down what was said
instead. Or scroll to *Write a story down* and type "teh lantern dissapeared ": autocorrect fixes both
words as you type. The retelling has a few emojis; the voice skips them.

## The 1:30 cut

Drop the low-burning-candle shot (keep 3 s of the wall) and the retelling, and shorten the Seance
to one meaning question and the "never given to me" answer.

## After recording

- [ ] Upload (YouTube unlisted, or anywhere DEV can embed), then put the link in `POST_DRAFT.md`
      (Demo) and `docs/index.html` (the demo box).
- [ ] The screenshots for the post are already in `docs/screenshots/` (taken from fictional stories).
      Swap in your own if you prefer.
- [ ] Turn Wi-Fi back on.
