// Ghostwriter page logic: Seance, the archive, story pages, the Archivist's voice.

import { $, el, localTime, present } from "./dom.js";
import { api, streamEvents } from "./api.js";
import { quill } from "./quill.js";
import { micProblem, startRecording } from "./recorder.js";

const IN_PROGRESS = ["queued", "transcribing", "thinking"];
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
    patience: "First the ghost listens, then it reads. It takes roughly a minute for every minute you spoke.",
    status: { queued: "waiting its turn...", transcribing: "the ghost is listening...",
              thinking: "the ghost is reading...", failed: "the ink ran dry" },
    tryAgain: "Try again",
    offering: "Offering it to the ghost...",
    accepted: "The ghost has it. It will write it down soon.",
    refused: "The ghost refused it: ",
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
    reaction: "",
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
    patience: "Transcribing with Whisper, then analysing with Gemma: roughly a minute per minute of audio.",
    status: { queued: "queued", transcribing: "transcribing...", thinking: "analysing...", failed: "failed" },
    tryAgain: "Retry",
    offering: "Uploading...",
    accepted: "Uploaded. Processing will finish shortly.",
    refused: "Upload failed: ",
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

async function askSeance(question) {
  const answer = $("#seance-answer");
  const sourcesLine = $("#seance-sources");
  const button = $("#seance-form button");
  sourcesLine.replaceChildren();
  answer.replaceChildren(el("p", { className: "status", textContent: voice().consulting }));
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
    });
  } catch (err) {
    showError(err.message);
  } finally {
    button.disabled = false;
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
  const box = el("div", { className: kind });
  const wrap = el("section", {}, el("h3", { textContent: heading }), note && el("p", { className: "meta", textContent: note }), box);
  const finish = (text) => {
    written.set(key, text);
    const button = speakButton(text);
    if (button) wrap.append(button);
  };
  const write = () => {
    const pen = quill(box);
    const showError = (message) => box.replaceChildren(
      el("p", { className: "error", textContent: voice().trouble + message }));
    streamEvents(`/api/stories/${story.id}/${kind}`, null, {
      token: (data) => pen.write(data.text),
      done: () => finish(pen.finish()),
      error: (data) => showError(data.message),
    }).catch((err) => showError(err.message));
  };
  const known = written.get(key) ?? story[kind];
  if (known) {
    box.append(el("p", { className: "handwriting", textContent: known }));
    finish(known);
  } else if (startNow) {
    write();
  } else {
    box.append(el("button", { textContent: voice().retell, onclick: write }));
  }
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
      const s = Math.floor((Date.now() - started) / 1000);
      button.textContent = `${voice().stop} (${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")})`;
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

function renderStory(s) {
  const e = s.entities || {};
  const v = voice();
  return present([
    el("a", { href: "#/", className: "meta", textContent: v.back }),
    el("h2", { textContent: statusText(s) }),
    IN_PROGRESS.includes(s.status) && el("p", { className: "status", textContent: v.patience }),
    Boolean(s.is_sample) && el("p", { className: "meta", textContent: "A fictional sample story, written for the demo." }),
    s.answers && el("p", { className: "meta" }, "An answer to: ",
      el("a", { href: `#/story/${s.answers.story_id}`, textContent: s.answers.text })),
    s.status === "failed" && el("p", { className: "error", textContent: s.error }),
    s.status === "failed" && el("button", { textContent: v.tryAgain, onclick: () => retry(s.id) }),
    !plain && s.status === "ready" && writtenBlock(s, "reaction", { heading: v.reaction, startNow: true }),
    s.summary && el("p", { textContent: s.summary }),
    s.audio_original && el("audio", { controls: true, preload: "none", src: `/api/stories/${s.id}/audio` }),
    el("dl", { className: "details" },
      ...entityRow("People", e.person),
      ...entityRow("Places", e.place),
      ...entityRow("When", e.era),
      ...entityRow("Keepsakes", e.keepsake),
      ...entityRow("Mood", s.mood && [s.mood]),
    ),
    s.questions.length > 0 && el("section", { className: "unfinished" },
      el("h3", { textContent: v.unfinished }),
      v.unfinishedHint && el("p", { className: "hint", textContent: v.unfinishedHint }),
      v.unfinishedIntro && el("p", { className: "handwriting", textContent: v.unfinishedIntro }),
      el("ul", { className: "questions" }, ...s.questions.map(questionItem)),
    ),
    s.status === "ready" && writtenBlock(s, "retelling", { heading: v.retelling, note: v.retellingNote, startNow: false }),
    s.transcript && el("details", {},
      el("summary", { textContent: `${v.transcript} (${s.language || "?"})` }),
      el("p", { className: "transcript", textContent: s.transcript }),
    ),
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
    page.replaceChildren(el("p", { className: "handwriting", textContent: voice().missing }));
    return null;
  }
}

// --------------------------------------------------------------------------- actions

async function upload(file, answersQuestionId) {
  const form = new FormData();
  form.append("file", file);
  if (answersQuestionId) form.append("answers_question_id", answersQuestionId);
  const status = $("#upload-status");
  status.textContent = voice().offering;
  try {
    const { id } = await api("/api/stories", { method: "POST", body: form });
    status.textContent = voice().accepted;
    location.hash = `#/story/${id}`;
  } catch (err) {
    status.textContent = voice().refused + err.message;
  }
}

async function retry(id) {
  await api(`/api/stories/${id}/retry`, { method: "POST" });
  refresh(true);
}

// Re-render the list (and the open story if it may have changed); poll while anything is processing.
let pollTimer = null;
async function refresh(force = false) {
  clearTimeout(pollTimer);
  const stories = await loadStories();
  const id = Number(location.hash.match(/^#\/story\/(\d+)$/)?.[1]) || null;
  if (id === null) {
    if (shown.id !== null) window.scrollTo({ top: 0, behavior: "smooth" });
    $("#story").hidden = true;
    shown = { id: null, status: null };
  } else if (force || id !== shown.id || IN_PROGRESS.includes(shown.status)) {
    const isNew = id !== shown.id;
    const story = await showStory(id);
    shown = { id, status: story?.status ?? null };
    if (isNew) {
      $("#story").scrollIntoView({ behavior: "smooth", block: "start" });
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
  });
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
    if (file) upload(file);
  });
  window.addEventListener("hashchange", () => refresh());
  haunt();

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
