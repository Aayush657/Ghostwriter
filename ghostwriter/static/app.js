// Ghostwriter UI (Stage 1): upload, archive list, story page.
// Plain JavaScript, no libraries, and it only ever talks to this local app.

const $ = (selector) => document.querySelector(selector);

const IN_PROGRESS = ["queued", "transcribing", "thinking"];
const STATUS_TEXT = {
  queued: "waiting its turn...",
  transcribing: "the ghost is listening...",
  thinking: "the ghost is reading...",
  failed: "the ink ran dry",
};

// Build DOM nodes. Text always goes in via textContent, so stories can never inject HTML.
// Empty children (null, false, "") are skipped, which keeps `condition && el(...)` readable.
const present = (children) => children.filter((c) => c !== null && c !== undefined && c !== false && c !== "");

function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  Object.assign(node, props);
  node.append(...present(children));
  return node;
}

// SQLite stores UTC ("2026-10-28 10:47:38"); show it in the viewer's own time zone.
const localTime = (utc) => new Date(utc.replace(" ", "T") + "Z").toLocaleString();

async function api(path, options) {
  const res = await fetch(path, options);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `${res.status} ${res.statusText}`);
  return body;
}

async function loadHealth() {
  const checks = await api("/api/health");
  $("#health").replaceChildren(...checks.map((c) => el("li", {
    className: c.ok ? "ok" : c.required ? "bad" : "off",
    title: c.ok ? c.detail : `${c.detail}. ${c.fix}`,
    textContent: c.name,
  })));
}

function storyLabel(s) {
  return s.status === "ready" ? s.title : STATUS_TEXT[s.status] || s.status;
}

async function loadStories() {
  const stories = await api("/api/stories");
  $("#story-list").replaceChildren(...stories.map((s) => el("li", {},
    el("a", { href: `#/story/${s.id}`, textContent: storyLabel(s) }),
    el("div", { className: "meta", textContent: [localTime(s.created_at), s.mood, s.language].filter(Boolean).join(" · ") }),
  )));
  return stories;
}

function entityRow(label, values) {
  if (!values || values.length === 0) return [];
  return [el("dt", { textContent: label }), el("dd", { textContent: values.join(", ") })];
}

async function showStory(id) {
  const s = await api(`/api/stories/${id}`);
  const page = $("#story");
  const e = s.entities || {};
  page.hidden = false;
  page.replaceChildren(...present([
    el("h2", { textContent: storyLabel(s) }),
    s.status === "failed" && el("p", { className: "error", textContent: s.error }),
    s.status === "failed" && el("button", { textContent: "Try again", onclick: () => retry(s.id) }),
    s.summary && el("p", { textContent: s.summary }),
    el("audio", { controls: true, preload: "none", src: `/api/stories/${s.id}/audio` }),
    el("dl", { className: "details" },
      ...entityRow("People", e.person),
      ...entityRow("Places", e.place),
      ...entityRow("When", e.era),
      ...entityRow("Keepsakes", e.keepsake),
      ...entityRow("Mood", s.mood && [s.mood]),
    ),
    s.questions.length > 0 && el("h3", { textContent: "Unfinished business" }),
    s.questions.length > 0 && el("ul", { className: "questions" }, ...s.questions.map(questionItem)),
    s.transcript && el("details", {},
      el("summary", { textContent: `Transcript (${s.language || "?"})` }),
      el("p", { className: "transcript", textContent: s.transcript }),
    ),
  ]));
  return s;
}

function questionItem(q) {
  if (q.answered_by) {
    return el("li", {}, q.text, " ", el("a", { href: `#/story/${q.answered_by}`, textContent: "(answered)" }));
  }
  const picker = el("input", { type: "file", accept: ".wav,.mp3,.m4a,.webm,.ogg", hidden: true });
  picker.onchange = () => picker.files[0] && upload(picker.files[0], q.id);
  return el("li", {}, q.text, " ", el("button", { textContent: "Answer", onclick: () => picker.click() }), picker);
}

async function upload(file, answersQuestionId) {
  const form = new FormData();
  form.append("file", file);
  if (answersQuestionId) form.append("answers_question_id", answersQuestionId);
  $("#upload-status").textContent = "Offering it to the ghost...";
  try {
    const { id } = await api("/api/stories", { method: "POST", body: form });
    $("#upload-status").textContent = "The ghost has it. It will write it down soon.";
    location.hash = `#/story/${id}`;
  } catch (err) {
    $("#upload-status").textContent = `The ghost refused it: ${err.message}`;
  }
}

async function retry(id) {
  await api(`/api/stories/${id}/retry`, { method: "POST" });
  refresh();
}

// Re-render the list and the open story; keep polling while anything is still being processed.
let pollTimer = null;
async function refresh() {
  clearTimeout(pollTimer);
  const stories = await loadStories();
  const match = location.hash.match(/^#\/story\/(\d+)$/);
  let open = null;
  if (match) open = await showStory(Number(match[1])).catch(() => null);
  else $("#story").hidden = true;
  const busy = stories.some((s) => IN_PROGRESS.includes(s.status));
  if (busy || (open && IN_PROGRESS.includes(open.status))) pollTimer = setTimeout(refresh, 2000);
}

$("#upload-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const file = event.target.file.files[0];
  if (file) upload(file);
});
window.addEventListener("hashchange", refresh);

loadHealth().catch(() => {});
refresh();
