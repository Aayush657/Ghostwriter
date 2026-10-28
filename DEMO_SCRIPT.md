# Ghostwriter: demo video script (2:00, with a 1:30 cut)

**The one rule:** every shot is real. The only cut is the processing wait, and the video says so on
screen. Don't speed anything up without a caption.

## Before you record

- [ ] Models already downloaded (`selfcheck` all green). Nothing can be fetched once Wi-Fi is off.
- [ ] Start the archive you'll show: `scripts\demo.ps1` (the fictional samples) or `scripts\run.ps1`
      (your real stories). Using the demo archive? Say on screen that the samples are fictional.
- [ ] Warm Gemma **just before** recording: `.venv\Scripts\python.exe -m ghostwriter.selfcheck --ping`.
      Ollama unloads the model after 5 idle minutes, and a cold load adds ~16 s.
- [ ] Practise the Seance questions once, so the stories they need exist and the answers are good.
      Then pick a story with no cached reaction for the live "Archivist writes" shot (a new recording
      is always fresh).
- [ ] Browser: full screen (F11), zoom 110-125% so the handwriting is readable on a phone.
- [ ] Screen recorder: OBS Studio (open source, fits the theme) or Windows' Snipping Tool video.
      **Capture system audio**, or the ghost's voice won't be in the video.
- [ ] Room: lights off, one real diya or candle beside the laptop if you have one. A phone on a
      stand for the room shots.
- [ ] Optional but worth everything: someone in your family, ready for the last shot (ask first).

## The script

| Time | Shot | What happens on screen | Voice-over (yours) / caption |
|---|---|---|---|
| 0:00-0:08 | **Room, phone camera.** Dark room, laptop glowing, a candle beside it. | The candle wall on screen. | VO: "The best stories in my family were never written down. So I built a ghost to keep them." |
| 0:08-0:18 | **Close-up of the taskbar**, then the terminal. | Turn Wi-Fi off (or airplane mode) on camera. Run `python -m ghostwriter.selfcheck`: all green. | Caption: **Wi-Fi: off.** VO: "Everything you're about to see runs on this laptop. No internet, no cloud, no API key." |
| 0:18-0:30 | **Screen.** Candle wall. | The greeting in handwriting; a whisper fades in. Hover the faint candle at the end. | VO: "Every candle is a story. The ones I haven't visited are burning low." |
| 0:30-0:45 | **Screen.** "Give the ghost a story". | Click *Speak, and the ghost will listen*. Tell a 10-15 second story, in Hinglish if that's how you talk. Click stop. An unlit candle appears with a curl of smoke. | Caption on the cut: **"About a minute later. Whisper and Gemma, both on the CPU."** |
| 0:45-1:05 | **Screen.** The new story's page. | Title and English summary of what you said. *The Archivist writes* streams in, word by word. Scroll to *Unfinished business: You never told me...* | VO: "Gemma wrote it down, understood my Hinglish, and asked about the part I skipped." |
| 1:05-1:25 | **Screen.** Seance. | Ask something your stories answer (e.g. "What did Nani cook?"): handwriting with a link to the story. Then ask something you never told it: *"That memory was never given to me."* | VO: "It only answers from what I told it. When it doesn't know, it says so." |
| 1:25-1:38 | **Screen.** | Click *Let the Archivist speak*. Let the ghost voice play for 5-8 s. Optional: click *Retell it as a ghost story* and show the first lines. | (Let the voice speak. No VO.) |
| 1:38-1:52 | **Room, phone camera.** | **The real moment:** someone hearing their own story read back by the ghost. | [PLACEHOLDER: what actually happened. Don't stage it; if it doesn't happen, cut this shot.] |
| 1:52-2:00 | **End card.** | "Ghostwriter: the ghost that keeps your stories. Gemma 4, Whisper, Piper. Fully offline." Repo and .tech links. | VO: "Tell it something true. It's listening." |

## The 1:30 cut

Drop the whispers shot (0:18-0:30, keep 3 s of the wall) and the retelling, and shorten the Seance
to the "never given to me" answer alone.

## After recording

- [ ] Upload (YouTube unlisted, or anywhere DEV can embed), then put the link in `POST_DRAFT.md`
      (Demo) and `docs/index.html` (the demo box).
- [ ] Take 3 screenshots for the post: the candle wall, a Seance answer with its citation, a story page
      with *Unfinished business*.
- [ ] Turn Wi-Fi back on.
