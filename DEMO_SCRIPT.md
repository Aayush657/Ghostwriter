# Ghostwriter: demo video script (about 2:30)

**The one rule:** every shot is real. The only cuts are waits (processing, writing), and the video says
so on screen. Don't speed anything up without a caption.

## Before you record

- [ ] Close everything else (Gemma and Whisper need the RAM). Turn on Do Not Disturb.
- [ ] Start Ollama (Start menu > Ollama), then in the project folder:
      `powershell -ExecutionPolicy Bypass -File scripts\demo.ps1`
- [ ] Open http://127.0.0.1:8000 in Chrome a minute early. Wait for "The Archivist is awake."
- [ ] Decide which stories are on the wall. The samples are fictional (the page says so); delete any
      test stories you don't want on camera.
- [ ] Prepare the slow parts ahead of time, so they play instantly on camera:
  - open the lantern sample, press **Retell it as a ghost story**, wait for it to finish, then press
    **Let the Archivist speak** once (the voice is made and kept);
  - ask the two Seance questions below once.
- [ ] Rehearse your story once: 15-25 seconds, in English, real, with a name and a place in it.
- [ ] Chrome: full screen (F11), zoom 110-125% (Ctrl +) so text reads on a phone.
- [ ] Recorder (OBS or Snipping Tool): capture **system audio**, or the Archivist's voice is lost.
- [ ] Room: lights low, a real candle or a jack-o'-lantern beside the laptop. A phone on a stand for
      the room shots. Quiet, close to the microphone for your story.

## The script

| Time | Shot | On screen | Voice-over (yours) / caption |
|---|---|---|---|
| 0:00-0:10 | **Room (phone).** Dark room, laptop glowing, candle. | The candle wall. | VO: "The best stories in my family were never written down. So I built a ghost to keep them." |
| 0:10-0:20 | **Screen.** Taskbar, then the About panel. | Turn Wi-Fi off. Open **About**: every local tool says "working". | Caption: **Wi-Fi: off.** VO: "Everything you're about to see runs on this laptop. No internet, no cloud, no account." |
| 0:20-0:32 | **Screen.** Candle wall. | Hover the scarecrow candle ("Not opened for ... days"), then the mood legend. | VO: "Every story is a candle. Its mood picks the candle, and the ones I haven't opened in a while burn low." |
| 0:32-0:48 | **Screen.** "Give the Archivist a story". | **Record a story**, tell your 15-25 s story (the clock and level meter run), **Stop and keep it**. The steps appear. | Caption on the cut: **"About a minute later. Whisper and Gemma, both on the CPU."** |
| 0:48-1:08 | **Screen.** Your new story. | The title, **The Archivist writes**, press **Let the Archivist speak** for a sentence or two, then the summary, the tags and **Unfinished business**. | VO: "It wrote my story down, noted who and where, and asked about the part I skipped." |
| 1:08-1:20 | **Screen.** "Write a story down". | Type: `teh lantern dissapeared. maya said "dont tell." ` and watch it fix itself. | VO: "No microphone? Write it instead. Even the autocorrect runs on the laptop." |
| 1:20-1:45 | **Screen.** Seance. | Ask **"Which relative loved telling tall tales?"**: the answer writes itself in, with a numbered source. Then ask **"What is the capital of France?"**: *"That memory was never given to me."* | VO: "It finds stories by meaning, and it only answers from what I told it. When it doesn't know, it says so." |
| 1:45-2:05 | **Screen.** The lantern sample. | Scroll to **A haunted retelling** (prepared earlier), press **Let the Archivist speak**. | (Let the voice speak. No VO.) |
| 2:05-2:15 | **Screen.** | **Open the memory book**, scroll a little. | VO: "And everything exports to one page that any browser can open, years from now." |
| 2:15-2:25 | **Room (phone).** Optional. | **The real moment:** someone hearing their own story. | [Only if it really happens. Don't stage it; if it doesn't, cut this shot.] |
| 2:25-2:35 | **End card.** | "Ghostwriter: the ghost that keeps your stories" · theghostwriter.tech · github.com/Aayush657/Ghostwriter · "Gemma 4, EmbeddingGemma, Whisper and Piper. Fully offline." | VO: "Tell it something true. It's listening." |

If you need it shorter (about 1:45): drop the memory book shot and the France question, and keep 5 s
of the retelling.

## After recording

- [ ] Edit (Clipchamp is built into Windows 11): cut the waits, add the two captions and the end card.
- [ ] Export 1080p MP4, upload to YouTube (Unlisted is fine; DEV can embed it), copy the link.
- [ ] Put the link in `POST_DRAFT.md` (Demo), `docs/index.html` (the demo box) and `README.md`.
- [ ] Turn Wi-Fi back on.
