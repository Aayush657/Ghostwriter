// Ghostwriter page logic: Seance, the archive, story pages, the Archivist's voice.

import { $, el, localTime, present } from "./dom.js";
import { api, send, streamEvents } from "./api.js";
import { quill } from "./quill.js";
import { micProblem, startRecording } from "./recorder.js";

const IN_PROGRESS = ["queued", "transcribing", "thinking", "noting"];
const AUDIO_TYPES = ".wav,.mp3,.m4a,.webm,.ogg";

// Everything the page says, in the Archivist's voice and in plain mode.
const VOICE = {
  ghost: {
    greeting: (n) => n === 0
      ? "The archive is empty, and so very quiet. Tell me something, my dear."
      : `Ah... you have returned. I keep ${n} of your memories.`,
    seance: "Séance",
    seanceHint: "Ask a question about your stories",
    askPlaceholder: "Ask the archive about a person, a place, a time...",
    ask: "Summon",
    askHint: "ask",
    consulting: "The candles lean. The Archivist is searching the shelves...",
    sources: "Consulted:",
    trouble: "The candle gutters. ",
    speak: "Let the Archivist speak",
    unwell: "Something in the walls is not well. The archive may only half wake:",
    give: "Give the ghost a story",
    giveHint: "Record or upload a story",
    record: "Speak, and the ghost will listen",
    micHint: "Your browser will ask to use the microphone. The recording stays on this computer.",
    stop: "Stop. Let the ghost keep it",
    orUpload: "...or offer a recording you already have:",
    offer: "Offer it",
    offerHint: "upload recording",
    archive: "The candle wall",
    archiveHint: "Your stories",
    filterLabel: "Show only memories about",
    allMemories: "every memory",
    emptyWall: "No candles yet. The wall waits for its first memory.",
    emptyAction: "Give the ghost its first story",
    filterEmpty: "No memory matches that.",
    book: "Open the memory book (to print or keep)",
    reaction: "The Archivist writes",
    unfinished: "Unfinished business",
    unfinishedHint: "Questions to fill the gaps",
    unfinishedIntro: "You never told me...",
    answer: "Speak your answer",
    answerFile: "or offer a file",
    answered: "answered",
    transcript: "The words as they were spoken",
    missing: "That memory was never given to me.",
    back: "← back to the candle wall",
    retelling: "A haunted retelling",
    retellingNote: "Told by the Archivist beside a dying fire. A retelling, not the memory itself, which stays exactly as you gave it.",
    retell: "Retell it as a ghost story",
    patience: "This takes about a minute for every minute you spoke. You can leave this page; the ghost keeps working.",
    status: { queued: "waiting its turn...", transcribing: "the ghost is listening...",
              thinking: "the ghost is reading...", noting: "the ghost is writing its note...", failed: "the ink ran dry" },
    stages: { transcribing: "Listening (writing down your words)", thinking: "Reading (title, summary, tags)",
              noting: "Writing the note" },
    tryAgain: "Try again",
    offering: "Offering it to the ghost...",
    accepted: "The ghost has your story. Watch it being written down",
    refused: "The ghost refused it: ",
    cancel: "Cancel",
    stopped: "Stopped. Nothing new was kept.",
    seanceStopped: "The candles are snuffed. The séance has ended.",
    emptyQuestion: "Ask me something first, my dear: a name, a place, a time.",
    writingNote: "The Archivist is writing its note...",
    writingRetelling: "The Archivist is telling it anew...",
    writeNote: "Write the note now",
    retellAgain: "Retell it again",
    retellAgainTitle: "Tell it anew?",
    retellAgainText: "The Archivist will tell this memory again, and this telling will be replaced. Your story itself is never changed.",
    retellAgainOk: "Tell it anew",
    rename: "Rename",
    renameLabel: "New title",
    save: "Save",
    cancelEdit: "Cancel",
    editWords: "Correct the words",
    edited: "You corrected these words. Whisper's original transcript is kept too.",
    rereadOffer: "The words are kept. Shall the ghost read them again, for a new title, summary, tags and questions?",
    reread: "Let the ghost re-read it",
    notNow: "Not now",
    editTags: "Edit tags",
    tagsHint: "Rename a tag to fix it. Give it the same name as another tag to merge them. Clear it to remove it.",
    deleteStory: "Delete this memory",
    deleteTitle: "Burn this memory?",
    deleteText: "The recording, the transcript, the Archivist's note and the retelling will all be gone, for good.",
    deleteOk: "Delete it forever",
    keepIt: "Keep it",
    deleted: "The memory has been laid to rest.",
  },
  plain: {
    greeting: (n) => `${n} ${n === 1 ? "story" : "stories"} saved.`,
    seance: "Ask your stories",
    seanceHint: "",
    askPlaceholder: "Ask about a person, a place or a time",
    ask: "Ask",
    askHint: "",
    consulting: "Searching your stories...",
    sources: "Sources:",
    trouble: "Error: ",
    speak: "Read aloud",
    reaction: "AI note",
    unwell: "Some local services are not available:",
    give: "Add a story",
    giveHint: "",
    record: "Record",
    micHint: "Your browser will ask to use the microphone. The recording stays on this computer.",
    stop: "Stop and save",
    orUpload: "Or upload an audio file:",
    offer: "Upload",
    offerHint: "",
    archive: "Stories",
    archiveHint: "",
    filterLabel: "Show only stories about",
    allMemories: "All stories",
    emptyWall: "No stories yet.",
    emptyAction: "Add your first story",
    filterEmpty: "No story matches that filter.",
    book: "Export all stories (printable)",
    unfinished: "Follow-up questions",
    unfinishedHint: "",
    unfinishedIntro: "",
    answer: "Record an answer",
    answerFile: "or upload a file",
    answered: "answered",
    transcript: "Transcript",
    missing: "Story not found.",
    back: "← all stories",
    retelling: "Ghost-story retelling",
    retellingNote: "A creative retelling written by Gemma. The original story is unchanged.",
    retell: "Retell as a ghost story",
    patience: "Roughly a minute per minute of audio. You can leave this page; processing continues.",
    status: { queued: "queued", transcribing: "transcribing...", thinking: "analysing...", noting: "writing the AI note...", failed: "failed" },
    stages: { transcribing: "Transcribing (Whisper)", thinking: "Analysing (Gemma)", noting: "Writing the AI note (Gemma)" },
    tryAgain: "Retry",
    offering: "Uploading...",
    accepted: "Uploaded. Open the story",
    refused: "Upload failed: ",
    cancel: "Cancel",
    stopped: "Stopped.",
    seanceStopped: "Stopped.",
    emptyQuestion: "Type a question first.",
    writingNote: "Writing the AI note...",
    writingRetelling: "Writing the retelling...",
    writeNote: "Write the AI note",
    retellAgain: "Retell again",
    retellAgainTitle: "Replace the retelling?",
    retellAgainText: "A new retelling will replace this one. The story itself is not changed.",
    retellAgainOk: "Replace it",
    rename: "Rename",
    renameLabel: "New title",
    save: "Save",
    cancelEdit: "Cancel",
    editWords: "Edit transcript",
    edited: "Edited. The original transcript is kept too.",
    rereadOffer: "Saved. Analyse the edited transcript again (title, summary, tags, questions)?",
    reread: "Analyse again",
    notNow: "Not now",
    editTags: "Edit tags",
    tagsHint: "Rename a tag to fix it. Use the name of another tag to merge them. Clear it to remove it.",
    deleteStory: "Delete story",
    deleteTitle: "Delete this story?",
    deleteText: "The recording, transcript, AI note and retelling will be permanently deleted.",
    deleteOk: "Delete",
    keepIt: "Cancel",
    deleted: "Story deleted.",
  },
};

let plain = false;
const voice = () => VOICE[plain ? "plain" : "ghost"];

// --------------------------------------------------------------------------- plain mode

function loadPlainPreference(fallback) {
  try {
    const saved = localStorage.getItem("ghostwriter.plain");
    return saved === null ? fallback : saved === "1";
  } catch {
    return fallback; // storage can be blocked; the default still works
  }
}

function savePlainPreference() {
  try { localStorage.setItem("ghostwriter.plain", plain ? "1" : "0"); } catch { /* not essential */ }
}

function applyVoice() {
  document.body.classList.toggle("plain", plain);
  document.querySelectorAll("[data-voice]").forEach((node) => {
    node.textContent = voice()[node.dataset.voice];
  });
  $("#seance-form").question.placeholder = voice().askPlaceholder;
}

// --------------------------------------------------------------------------- health

async function loadHealth() {
  const checks = await api("/api/health");
  const state = (c) => (c.ok ? "working" : c.required ? "missing" : "optional, not set up");
  $("#health").replaceChildren(...checks.map((c) => el("li", {
    className: c.ok ? "ok" : c.required ? "bad" : "off",
    title: c.ok ? c.detail : `${c.detail}. ${c.fix}`,
    ariaLabel: `${c.name}: ${state(c)}`,
    textContent: c.name,
  })));
  voiceReady = checks.some((c) => c.name === "Piper TTS" && c.ok);
  const broken = checks.filter((c) => c.required && !c.ok);
  const banner = $("#health-banner");
  banner.hidden = broken.length === 0;
  banner.replaceChildren(
    el("p", { textContent: voice().unwell }),
    el("ul", {}, ...broken.map((c) => el("li", {},
      el("strong", { textContent: `${c.name}: ` }), `${c.detail}. `,
      c.fix && el("span", { className: "fix", textContent: `Fix: ${c.fix}` }),
    ))),
  );
}

// --------------------------------------------------------------------------- the Archivist's voice

let voiceReady = true; // corrected by the health check; if wrong, the click explains the fix
let playing = null;    // only one voice at a time

function speakButton(text) {
  if (!voiceReady) return null;
  const button = el("button", { className: "quiet speak", textContent: voice().speak });
  button.onclick = async () => {
    playing?.pause();
    button.parentElement.querySelector(".voice-error")?.remove();
    button.disabled = true;
    try {
      const res = await fetch("/api/speak", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, plain }),
      });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || res.statusText);
      playing = new Audio(URL.createObjectURL(await res.blob()));
      await playing.play();
    } catch (err) {
      button.after(el("p", { className: "error voice-error", textContent: voice().trouble + err.message }));
    } finally {
      button.disabled = false;
    }
  };
  return button;
}

// --------------------------------------------------------------------------- Seance

// --------------------------------------------------------------------------- waiting on Gemma

const mmss = (ms) => {
  const s = Math.max(0, Math.floor(ms / 1000));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
};

// A ticking "0:42". One timer (in start()) updates every clock on the page.
function clock(since = Date.now()) {
  const node = el("span", { className: "elapsed", textContent: mmss(Date.now() - since) });
  node.dataset.since = since;
  return node;
}

// "Working on it" line: what is happening, how long it has taken, and a Cancel button if it can stop.
const working = (text, onCancel) => el("p", { className: "status working", role: "status" },
  `${text} `, clock(), onCancel && el("button", { type: "button", className: "quiet", textContent: voice().cancel, onclick: onCancel }));

// --------------------------------------------------------------------------- Seance

let seanceRun = null; // the question being answered, so a new one (or Cancel) can stop it

function clearSeance() {
  seanceRun?.abort();
  seanceRun = null;
  $("#seance-answer").replaceChildren();
  $("#seance-sources").replaceChildren();
}

async function askSeance(question) {
  clearSeance();
  const answer = $("#seance-answer");
  const sourcesLine = $("#seance-sources");
  const button = $("#seance-form button");
  const run = seanceRun = new AbortController();
  sourcesLine.replaceChildren(working(voice().consulting, () => run.abort()));
  button.disabled = true;

  let sources = [];
  let pen = null;
  const showError = (message) =>
    answer.replaceChildren(el("p", { className: "error", textContent: voice().trouble + message }));
  try {
    await streamEvents("/api/seance", { question, plain }, {
      sources: (data) => { sources = data.stories; },
      token: (data) => { pen ??= quill(answer); pen.write(data.text); },
      error: (data) => showError(data.message),
      done: (data) => {
        const titles = new Map(sources.map((s) => [s.id, s.title]));
        const cited = new Set(data.cited);
        const text = pen?.finish((id) => (cited.has(id) ? { href: `#/story/${id}`, label: titles.get(id) } : null));
        sourcesLine.replaceChildren(...present([
          cited.size > 0 && `${voice().sources} `,
          ...[...cited].flatMap((id, i) => [
            i > 0 ? ", " : "", el("a", { href: `#/story/${id}`, textContent: titles.get(id) }),
          ]),
          text && " ",
          text && speakButton(text),
        ]));
      },
    }, run.signal);
  } catch (err) {
    if (err.name !== "AbortError") showError(err.message);
    else if (run === seanceRun) { answer.replaceChildren(el("p", { className: "status", textContent: voice().seanceStopped })); sourcesLine.replaceChildren(); }
  } finally {
    if (seanceRun === null || run === seanceRun) button.disabled = false;
  }
}

// --------------------------------------------------------------------------- the candle wall

const statusText = (s) => (s.status === "ready" ? s.title : voice().status[s.status] || s.status);

const FADE_DAYS = 30; // an unvisited candle burns down to a faint glow over about a month
const ENTITY_GROUPS = [["person", "People"], ["place", "Places"], ["era", "When"]];

let allStories = [];
let wallKey = ""; // skip re-rendering (and restarting the flame animations) when nothing changed

const daysSinceVisit = (story) => (Date.now() - Date.parse(story.last_visited_at.replace(" ", "T") + "Z")) / 86_400_000;
const life = (story) => Math.min(1, Math.max(0.12, 1 - daysSinceVisit(story) / FADE_DAYS));

function lastOpened(story) {
  const days = Math.floor(daysSinceVisit(story));
  return days < 1 ? "Opened today." : `Not opened for ${days} day${days === 1 ? "" : "s"}: its candle burns lower.`;
}

// Each mood has its own candle design and flame colour (style.css, .mood-*); see models.Mood.
const MOODS = ["joyful", "nostalgic", "loving", "poignant", "mysterious", "eerie"];
const moodOf = (s) => (MOODS.includes(s.mood?.toLowerCase()) ? s.mood.toLowerCase() : "nostalgic"); // older free-form moods
const hasMood = (mood) => allStories.some((s) => s.status === "ready" && moodOf(s) === mood);

function candle(s, i = 0) {
  const lit = s.status === "ready";
  const mood = moodOf(s);
  const meta = [localTime(s.created_at), s.mood, s.is_sample && "fictional sample"].filter(Boolean).join(" · ");
  const tooltip = [s.summary, lit && lastOpened(s)].filter(Boolean).join("\n");
  const node = el("a", { href: `#/story/${s.id}`, className: `candle mood-${mood} ${lit ? "lit" : s.status}`, title: tooltip },
    el("span", { className: "art" },
      el("span", { className: "holder" }),
      el("span", { className: "wax" }),
      el("span", { className: "wick" }),
      el("span", { className: "flame-wrap" }, el("span", { className: "flame" })),
    ),
    el("span", { className: "label", textContent: statusText(s) }),
    el("span", { className: "meta", textContent: meta }),
  );
  node.style.setProperty("--life", lit ? life(s).toFixed(2) : "0");
  node.style.setProperty("--i", i); // candles rise onto the wall one after another
  return node;
}

function renderFilterOptions() {
  const select = $("#filter");
  const current = select.value;
  const groups = ENTITY_GROUPS.map(([kind, label]) => {
    const values = [...new Set(allStories.flatMap((s) => s.entities?.[kind] || []))].sort();
    return values.length && el("optgroup", { label },
      ...values.map((v) => el("option", { value: `${kind}:${v}`, textContent: v })));
  });
  const moods = MOODS.filter(hasMood);
  groups.push(moods.length > 0 && el("optgroup", { label: "Mood" },
    ...moods.map((m) => el("option", { value: `mood:${m}`, textContent: m }))));
  select.replaceChildren(el("option", { value: "", textContent: voice().allMemories }), ...present(groups));
  select.value = [...select.options].some((o) => o.value === current) ? current : "";
}

function renderWall() {
  const filter = $("#filter").value;
  const split = filter.indexOf(":");
  const [kind, value] = [filter.slice(0, split), filter.slice(split + 1)];
  const matches = (s) => (kind === "mood" ? s.status === "ready" && moodOf(s) === value : s.entities?.[kind]?.includes(value));
  const shown = filter ? allStories.filter(matches) : allStories;
  const empty = allStories.length === 0
    ? [el("div", { className: "empty" },
        el("p", { className: "handwriting", textContent: voice().emptyWall }),
        el("a", { className: "button", href: "#new-story", textContent: voice().emptyAction,
                  onclick: (event) => { event.preventDefault(); $("#new-story").scrollIntoView({ behavior: "smooth" }); $("#record-button").focus(); } }))]
    : [el("p", { className: "meta", textContent: voice().filterEmpty })];
  $("#wall").replaceChildren(...(shown.length ? shown.map(candle) : empty));
  $("#archive").classList.toggle("is-empty", allStories.length === 0); // no filter or key until there's a candle
  // The colour key doubles as a mood filter: show which mood is lit, and which have no candles yet.
  document.querySelectorAll(".legend button").forEach((b) => {
    b.setAttribute("aria-pressed", String(filter === `mood:${b.dataset.mood}`));
    b.disabled = !hasMood(b.dataset.mood);
  });
}

// Suggested questions: the people, places and keepsakes that come up most often across the stories.
function renderChips() {
  const counts = new Map(); // lower-case name -> { name, n }
  for (const s of allStories.filter((s) => s.status === "ready")) {
    for (const kind of ["person", "place", "keepsake"]) {
      for (const raw of s.entities?.[kind] || []) {
        const name = raw.replace(/\s*\(.*\)$/, "").trim(); // "Nani (grandmother)" -> "Nani"
        const seen = counts.get(name.toLowerCase());
        if (name.length >= 3) counts.set(name.toLowerCase(), { name, n: (seen?.n || 0) + 1 });
      }
    }
  }
  // Most frequent first; on a tie, real names ("Jaipur", "Rohan") before relations ("father").
  const isName = (name) => name[0] !== name[0].toLowerCase();
  const ranked = [...counts.values()].sort((a, b) => b.n - a.n || isName(b.name) - isName(a.name));
  const top = [];
  for (const { name } of ranked) {
    const low = name.toLowerCase();
    if (top.some((t) => low.includes(t.toLowerCase()) || t.toLowerCase().includes(low))) continue; // "grandfather" vs "grandfather's father"
    top.push(name);
    if (top.length === 5) break;
  }
  $("#seance-chips").replaceChildren(...top.map((name) => el("button", {
    type: "button", className: "chip", textContent: `Ask about ${name}`,
    onclick: () => {
      const question = `Tell me about ${name}.`;
      $("#seance-form").question.value = question;
      askSeance(question);
    },
  })));
}

async function loadStories() {
  const stories = await api("/api/stories");
  const ready = stories.filter((s) => s.status === "ready").length;
  $("#greeting").textContent = voice().greeting(ready);
  const key = JSON.stringify(stories) + plain;
  if (key !== wallKey) {
    wallKey = key;
    allStories = stories;
    renderFilterOptions();
    renderWall();
    renderChips();
  }
  return stories;
}

// Opening a story relights its candle: the server records the visit, the flame grows back in place.
async function relight(id) {
  await api(`/api/stories/${id}/visit`, { method: "POST" }).catch(() => null);
  const story = allStories.find((s) => s.id === id);
  if (story) story.last_visited_at = new Date().toISOString().slice(0, 19).replace("T", " ");
  const node = document.querySelector(`.candle[href="#/story/${id}"]`);
  if (node && story?.status === "ready") {
    node.style.setProperty("--life", "1");
    node.classList.add("relit");
  }
}

// --------------------------------------------------------------------------- story page

const written = new Map(); // "reaction:3" -> finished text, so re-renders never re-ask Gemma

// Something Gemma writes once per story (the reaction, the retelling): replayed if already
// written, otherwise streamed in, either straight away or when the visitor asks for it.
function writtenBlock(story, kind, { heading, note, startNow }) {
  const key = `${kind}:${story.id}`;
  const v = voice();
  const box = el("div", { className: kind });
  const tools = el("div", { className: "tools" }); // speak, retell again, or the working line
  const wrap = el("section", {}, el("h3", { textContent: heading }), note && el("p", { className: "meta", textContent: note }), box, tools);
  const startLabel = kind === "retelling" ? v.retell : v.writeNote;
  const show = (text) => {
    written.set(key, text);
    box.replaceChildren(el("p", { className: "ghost-text", textContent: text }));
    tools.replaceChildren(...present([speakButton(text), kind === "retelling" && el("button", {
      type: "button", className: "quiet", textContent: v.retellAgain,
      onclick: async () => {
        const yes = await confirmDialog({ title: v.retellAgainTitle, text: v.retellAgainText, ok: v.retellAgainOk, cancel: v.cancelEdit });
        if (yes) write(true);
      },
    })]));
  };
  const offer = () => tools.replaceChildren(el("button", { type: "button", textContent: startLabel, onclick: () => write() }));
  // Stopped or failed: keep the earlier text if there was one, otherwise offer to start again.
  const fallBack = (message, isError) => {
    const before = written.get(key) ?? story[kind];
    if (before) show(before); else { box.replaceChildren(); offer(); }
    tools.prepend(el("p", { className: isError ? "error" : "status", textContent: message }));
  };
  const write = (again = false) => {
    const run = new AbortController();
    let pen = null;
    tools.replaceChildren(working(kind === "retelling" ? v.writingRetelling : v.writingNote, () => run.abort()));
    streamEvents(`/api/stories/${story.id}/${kind}${again ? "?again=true" : ""}`, null, {
      token: (data) => { pen ??= quill(box); pen.write(data.text); },
      done: () => show(pen ? pen.finish() : ""),
      error: (data) => fallBack(v.trouble + data.message, true),
    }, run.signal).catch((err) => fallBack(err.name === "AbortError" ? v.stopped : v.trouble + err.message, err.name !== "AbortError"));
  };
  const known = written.get(key) ?? story[kind];
  if (known) show(known);
  else if (startNow) write();
  else offer();
  return wrap;
}

function entityRow(label, values) {
  if (!values || values.length === 0) return [];
  return [el("dt", { textContent: label }), el("dd", { textContent: values.join(", ") })];
}

function questionItem(q) {
  if (q.answered_by) {
    return el("li", {}, q.text, " ", el("a", { href: `#/story/${q.answered_by}`, textContent: `(${voice().answered})` }));
  }
  const picker = el("input", { type: "file", accept: AUDIO_TYPES, hidden: true });
  picker.onchange = () => picker.files[0] && upload(picker.files[0], q.id);
  const speak = el("button", { textContent: voice().answer });
  speak.onclick = () => toggleRecording(speak, q.id);
  return el("li", {}, q.text, " ", speak, " ",
    el("button", { className: "quiet", textContent: voice().answerFile, onclick: () => picker.click() }), picker);
}

// --------------------------------------------------------------------------- recording

let recording = null; // the one recording in progress: { stop, button, label, timer, answersQuestionId }

async function toggleRecording(button, answersQuestionId = null) {
  button.parentElement.querySelector(".mic-error")?.remove();
  if (recording) {
    const { stop, button: active, label, timer, answersQuestionId: answering } = recording;
    recording = null;
    clearInterval(timer);
    active.textContent = label;
    active.classList.remove("live");
    upload(await stop(), answering);
    return;
  }
  try {
    const session = await startRecording();
    const label = button.textContent;
    const started = Date.now();
    const tick = () => {
      button.textContent = `${voice().stop} (${mmss(Date.now() - started)})`;
    };
    tick();
    button.classList.add("live");
    recording = { ...session, button, label, timer: setInterval(tick, 500), answersQuestionId };
  } catch (err) {
    const problem = micProblem(err);
    button.after(el("p", { className: "error mic-error",
      textContent: plain ? problem.fix : `${problem.ghost} ${problem.fix}` }));
  }
}

const TAG_KINDS = [["person", "People"], ["place", "Places"], ["era", "When"], ["keepsake", "Keepsakes"]];
const STAGES = ["transcribing", "thinking", "noting"];
const progressSince = new Map(); // story id -> when this page first saw it being processed
const editable = (s) => s.status === "ready" || s.status === "failed";

// Which step the ghost is on, and for how long. (Whisper can't be stopped halfway, so no Cancel here.)
function progress(s) {
  const v = voice();
  if (!progressSince.has(s.id)) progressSince.set(s.id, Date.now());
  const now = STAGES.indexOf(s.status);
  const done = (stage, i) => i < now || (stage === "transcribing" && Boolean(s.transcript));
  return el("div", { className: "progress", role: "status" },
    el("ol", { className: "stages" }, ...STAGES.map((stage, i) => el("li", {
      className: done(stage, i) ? "done" : i === now ? "now" : "",
      textContent: v.stages[stage],
    }))),
    el("p", { className: "status" }, s.status === "queued" ? `${v.status.queued} ` : "", clock(progressSince.get(s.id))),
    el("p", { className: "meta", textContent: v.patience }),
  );
}

// The title, with a Rename button that swaps it for a small form.
function titleRow(s) {
  const v = voice();
  const heading = el("h2", { tabIndex: -1, textContent: statusText(s) });
  if (!editable(s) || !s.title) return heading;
  const row = el("div", { className: "title-row" }, heading);
  row.append(el("button", { type: "button", className: "quiet", textContent: v.rename, onclick: () => {
    const input = el("input", { type: "text", value: s.title, maxLength: 120, required: true, ariaLabel: v.renameLabel });
    const form = el("form", { className: "inline-edit" }, input,
      el("button", { type: "submit", textContent: v.save }),
      el("button", { type: "button", className: "quiet", textContent: v.cancelEdit, onclick: () => form.replaceWith(row) }));
    form.onsubmit = (event) => { event.preventDefault(); saveStory(s.id, { title: input.value.trim() }, form); };
    row.replaceWith(form);
    input.select();
  } }));
  return row;
}

async function saveStory(id, changes, near) {
  near.querySelector(".error")?.remove();
  try {
    await send(`/api/stories/${id}`, "PATCH", changes);
    await refresh(true);
  } catch (err) {
    near.append(el("p", { className: "error", textContent: voice().trouble + err.message }));
  }
}

// People, places, eras and keepsakes, with an editor to rename, merge or remove them.
function tagsBlock(s) {
  const v = voice();
  const e = s.entities || {};
  const kinds = TAG_KINDS.filter(([kind]) => e[kind]?.length);
  const list = el("dl", { className: "details" },
    ...kinds.flatMap(([kind, label]) => entityRow(label, e[kind])), ...entityRow("Mood", s.mood && [s.mood]));
  if (!editable(s) || kinds.length === 0) return list;
  const wrap = el("div", { className: "tags" }, list);
  wrap.append(el("button", { type: "button", className: "quiet", textContent: v.editTags, onclick: () => {
    const fields = [];
    const form = el("form", { className: "tags-edit" },
      el("p", { className: "meta", textContent: v.tagsHint }),
      ...kinds.map(([kind, label]) => el("fieldset", {}, el("legend", { textContent: label }),
        ...e[kind].map((value) => {
          const input = el("input", { type: "text", value, maxLength: 80, ariaLabel: `${label}: ${value}` });
          fields.push({ kind, old: value, input });
          return input;
        }))),
      el("div", { className: "row" },
        el("button", { type: "submit", textContent: v.save }),
        el("button", { type: "button", className: "quiet", textContent: v.cancelEdit, onclick: () => form.replaceWith(wrap) })));
    form.onsubmit = async (event) => {
      event.preventDefault();
      form.querySelector(".error")?.remove();
      try {
        for (const { kind, old, input } of fields) {
          if (input.value.trim() !== old) await send(`/api/stories/${s.id}/tags`, "POST", { kind, old, new: input.value.trim() });
        }
        await refresh(true);
      } catch (err) {
        form.append(el("p", { className: "error", textContent: v.trouble + err.message }));
      }
    };
    wrap.replaceWith(form);
    fields[0].input.focus();
  } }));
  return wrap;
}

// "The words as they were spoken", with an editor; saving offers to let Gemma read them again.
function transcriptBlock(s) {
  const v = voice();
  const details = el("details", { className: "words" },
    el("summary", { textContent: `${v.transcript} (${s.language || "?"})` }),
    el("p", { className: "transcript", textContent: s.transcript }));
  if (s.transcript_original) details.append(el("p", { className: "meta", textContent: v.edited }));
  if (!editable(s)) return details;
  details.append(el("button", { type: "button", className: "quiet", textContent: v.editWords, onclick: () => {
    const box = el("textarea", { value: s.transcript, rows: 8, required: true, ariaLabel: v.transcript });
    const form = el("form", { className: "transcript-edit" }, box,
      el("div", { className: "row" },
        el("button", { type: "submit", textContent: v.save }),
        el("button", { type: "button", className: "quiet", textContent: v.cancelEdit, onclick: () => refresh(true) })));
    form.onsubmit = async (event) => {
      event.preventDefault();
      form.querySelector(".error")?.remove();
      try {
        await send(`/api/stories/${s.id}`, "PATCH", { transcript: box.value });
        form.replaceWith(el("div", { className: "reread", role: "status" },
          el("p", { textContent: v.rereadOffer }),
          el("button", { type: "button", textContent: v.reread, onclick: () => reread(s.id) }), " ",
          el("button", { type: "button", className: "quiet", textContent: v.notNow, onclick: () => refresh(true) })));
      } catch (err) {
        form.append(el("p", { className: "error", textContent: v.trouble + err.message }));
      }
    };
    details.replaceChildren(details.firstChild, form);
    box.focus();
  } }));
  return details;
}

function deleteButton(s) {
  const v = voice();
  return editable(s) && el("button", { type: "button", className: "danger", textContent: v.deleteStory, onclick: async () => {
    if (!await confirmDialog({ title: v.deleteTitle, text: v.deleteText, ok: v.deleteOk, cancel: v.keepIt })) return;
    try {
      await send(`/api/stories/${s.id}`, "DELETE");
      toast(v.deleted);
      location.hash = "#/";
    } catch (err) {
      toast(v.trouble + err.message);
    }
  } });
}

function renderStory(s) {
  const v = voice();
  return present([
    el("a", { href: "#/", className: "meta back", textContent: v.back }),
    titleRow(s),
    IN_PROGRESS.includes(s.status) && progress(s),
    Boolean(s.is_sample) && el("p", { className: "meta", textContent: "A fictional sample story, written for the demo." }),
    s.answers && el("p", { className: "meta" }, "An answer to: ",
      el("a", { href: `#/story/${s.answers.story_id}`, textContent: s.answers.text })),
    s.status === "failed" && el("p", { className: "error", textContent: s.error }),
    s.status === "failed" && el("button", { textContent: v.tryAgain, onclick: () => retry(s.id) }),
    s.status === "ready" && writtenBlock(s, "reaction", { heading: v.reaction, startNow: true }),
    s.summary && el("p", { className: "summary", textContent: s.summary }),
    s.audio_original && el("audio", { controls: true, preload: "metadata", src: `/api/stories/${s.id}/audio`, ariaLabel: "The original recording" }),
    tagsBlock(s),
    s.questions.length > 0 && el("section", { className: "unfinished" },
      el("h3", { textContent: v.unfinished }),
      v.unfinishedHint && el("p", { className: "hint", textContent: v.unfinishedHint }),
      v.unfinishedIntro && el("p", { className: "handwriting", textContent: v.unfinishedIntro }),
      el("ul", { className: "questions" }, ...s.questions.map(questionItem)),
    ),
    s.status === "ready" && writtenBlock(s, "retelling", { heading: v.retelling, note: v.retellingNote, startNow: false }),
    s.transcript && transcriptBlock(s),
    deleteButton(s),
  ]);
}

let shown = { id: null, status: null }; // the story on screen, so ready stories aren't re-rendered

async function showStory(id) {
  const page = $("#story");
  page.hidden = false;
  try {
    const story = await api(`/api/stories/${id}`);
    page.replaceChildren(...renderStory(story));
    return story;
  } catch {
    page.replaceChildren(
      el("a", { href: "#/", className: "meta back", textContent: voice().back }),
      el("h2", { tabIndex: -1, className: "handwriting", textContent: voice().missing }));
    return null;
  }
}

// --------------------------------------------------------------------------- dialogs and notices

// An in-page confirmation (a real <dialog>: keyboard and screen-reader friendly, Esc cancels).
function confirmDialog({ title, text, ok, cancel }) {
  const dialog = $("#confirm");
  $("#confirm-title").textContent = title;
  $("#confirm-text").textContent = text;
  $("#confirm-ok").textContent = ok;
  $("#confirm-cancel").textContent = cancel;
  dialog.returnValue = "";
  dialog.showModal();
  $("#confirm-cancel").focus(); // the safe choice is the default
  return new Promise((resolve) => dialog.addEventListener("close", () => resolve(dialog.returnValue === "ok"), { once: true }));
}

let toastTimer = null;
function toast(text) {
  const node = $("#toast");
  node.textContent = text;
  node.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { node.hidden = true; }, 5000);
}

// --------------------------------------------------------------------------- actions

let statusTimer = null;
async function upload(file, answersQuestionId, form = null) {
  const data = new FormData();
  data.append("file", file);
  if (answersQuestionId) data.append("answers_question_id", answersQuestionId);
  const status = $("#upload-status");
  const button = form?.querySelector("button");
  clearTimeout(statusTimer);
  status.replaceChildren(voice().offering);
  if (button) button.disabled = true;
  try {
    const { id } = await api("/api/stories", { method: "POST", body: data });
    form?.reset();
    status.replaceChildren(el("a", { href: `#/story/${id}`, textContent: voice().accepted }));
    statusTimer = setTimeout(() => status.replaceChildren(), 30000);
    location.hash = `#/story/${id}`;
  } catch (err) {
    status.replaceChildren(el("span", { className: "error", textContent: voice().refused + err.message }));
  } finally {
    if (button) button.disabled = false;
  }
}

async function retry(id) {
  await api(`/api/stories/${id}/retry`, { method: "POST" });
  refresh(true);
}

async function reread(id) {
  try {
    await api(`/api/stories/${id}/reread`, { method: "POST" });
    written.delete(`reaction:${id}`); // the note is rewritten for the new words
    progressSince.delete(id);
  } catch (err) {
    toast(voice().trouble + err.message);
  }
  refresh(true);
}

// The home page (candle wall, Seance, new story) and a story are separate views. Going back
// returns to where you were on the home page.
let homeScroll = null;
addEventListener("scroll", () => { if (!document.body.classList.contains("reading")) homeScroll = scrollY; }, { passive: true });

// Re-render the list (and the open story if it may have changed); poll while anything is processing.
let pollTimer = null;
async function refresh(force = false) {
  clearTimeout(pollTimer);
  const stories = await loadStories();
  const id = Number(location.hash.match(/^#\/story\/(\d+)$/)?.[1]) || null;
  if (id === null) {
    if (document.body.classList.contains("reading")) {
      const left = shown.id;
      document.body.classList.remove("reading");
      $("#story").hidden = true;
      if (homeScroll === null) $("#archive").scrollIntoView();
      else window.scrollTo(0, homeScroll);
      document.querySelector(`.candle[href="#/story/${left}"]`)?.focus({ preventScroll: true });
    }
    shown = { id: null, status: null };
  } else if (force || id !== shown.id || IN_PROGRESS.includes(shown.status)) {
    const isNew = id !== shown.id;
    document.body.classList.add("reading");
    const story = await showStory(id);
    shown = { id, status: story?.status ?? null };
    if (isNew) {
      window.scrollTo(0, 0);
      $("#story h2")?.focus({ preventScroll: true }); // keyboard and screen-reader users land on the title
      if (story) relight(id);
    }
  }
  if (stories.some((s) => IN_PROGRESS.includes(s.status))) pollTimer = setTimeout(refresh, 2000);
}

// --------------------------------------------------------------------------- whispers

// Sometimes (not always) the ghost murmurs a line from a faded story when the page opens.
async function maybeWhisper() {
  if (plain || Math.random() > 0.7) return;
  const res = await fetch("/api/whisper");
  if (res.status !== 200) return;
  const w = await res.json();
  const node = $("#whisper");
  node.replaceChildren(el("a", { href: `#/story/${w.story_id}`, title: w.title, textContent: `“${w.text}”` }));
  node.hidden = false;
  setTimeout(() => node.classList.add("fading"), 15000);
}

// --------------------------------------------------------------------------- the haunting (decoration only)

function haunt() {
  const lantern = document.querySelector(".lantern");
  if (matchMedia("(pointer: fine)").matches) {
    addEventListener("pointermove", (e) => {
      lantern.classList.add("on");
      lantern.style.transform = `translate(${e.clientX}px, ${e.clientY}px)`;
    }, { passive: true });
  }
  const ghost = $("#mascot");
  ghost.addEventListener("click", () => {
    ghost.classList.remove("boo");
    void ghost.offsetWidth; // restart the animation on every poke
    ghost.classList.add("boo");
  });
}

// --------------------------------------------------------------------------- start

async function start() {
  const defaults = await api("/api/settings").catch(() => ({}));
  plain = loadPlainPreference(Boolean(defaults.plain_mode_default));
  $("#plain-toggle").checked = plain;
  applyVoice();

  $("#plain-toggle").addEventListener("change", (event) => {
    plain = event.target.checked;
    savePlainPreference();
    applyVoice();
    loadHealth().catch(() => {});
    refresh(true);
  });
  $("#seance-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const question = event.target.question.value.trim();
    if (question) askSeance(question);
    else {
      clearSeance();
      $("#seance-answer").replaceChildren(el("p", { className: "status", textContent: voice().emptyQuestion }));
      event.target.question.focus();
    }
  });
  $("#seance-form").question.addEventListener("input", (event) => { if (!event.target.value.trim()) clearSeance(); });
  $("#record-button").addEventListener("click", (event) => toggleRecording(event.currentTarget));
  $("#filter").addEventListener("change", renderWall);
  $(".legend").addEventListener("click", (event) => {
    const mood = event.target.closest("button")?.dataset.mood;
    if (!mood) return;
    const select = $("#filter");
    select.value = select.value === `mood:${mood}` ? "" : `mood:${mood}`; // a second click shows every candle again
    renderWall();
  });
  $("#upload-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const file = event.target.file.files[0];
    if (file) upload(file, null, event.target);
  });
  window.addEventListener("hashchange", () => refresh());
  haunt();
  setInterval(() => document.querySelectorAll(".elapsed").forEach((node) => {
    node.textContent = mmss(Date.now() - Number(node.dataset.since));
  }), 1000);

  // The "how it works" strip, until the visitor hides it (remembered if storage is allowed).
  try { $("#how").hidden = localStorage.getItem("ghostwriter.howHidden") === "1"; } catch { /* show it */ }
  $("#how-close").addEventListener("click", () => {
    $("#how").hidden = true;
    try { localStorage.setItem("ghostwriter.howHidden", "1"); } catch { /* hidden for this visit only */ }
  });

  fetch("/api/warm", { method: "POST" }).catch(() => {}); // load Gemma before the first question
  loadHealth().catch(() => {});
  refresh();
  setTimeout(() => maybeWhisper().catch(() => {}), 2500);
}

start();
