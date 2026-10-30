// Ghostwriter page logic: the candle wall, story pages, the Seance, recording, the Archivist's voice.

import { $, el, localTime, present } from "./dom.js";
import { api, send, streamEvents } from "./api.js";
import { attachAutocorrect, storyBox } from "./autocorrect.js";
import { quill } from "./quill.js";
import { micProblem, startRecording } from "./recorder.js";

const IN_PROGRESS = ["queued", "transcribing", "thinking", "noting"];
const AUDIO_EXTENSIONS = [".wav", ".mp3", ".m4a", ".webm", ".ogg"];
const AUDIO_TYPES = AUDIO_EXTENSIONS.join(",");

// --------------------------------------------------------------------------- moods
// One map for the legend, the filter and the candles. The server's list is models.Mood; style.css
// draws each design (.mood-*). tests/test_frontend.py checks the two lists match.
const MOODS = {
  joyful: { shape: "jack-o'-lantern", flame: "gold" },
  nostalgic: { shape: "dripping pillar candle", flame: "amber" },
  loving: { shape: "clay oil lamp", flame: "rose" },
  poignant: { shape: "twisted taper", flame: "blue" },
  mysterious: { shape: "iron lantern", flame: "violet" },
  eerie: { shape: "skull candle", flame: "green" },
};
const FALLBACK_MOOD = "nostalgic";

// --------------------------------------------------------------------------- copy
// Every word the page says, in the Archivist's voice (spooky) and in plain mode. Nothing user-facing
// is written anywhere else, so plain mode is complete. [data-voice="key"] elements in index.html get
// their text from here; [data-voice-placeholder] and [data-voice-title] their placeholder and tooltip.
const COPY = {
  spooky: {
    tagline: "The ghost that keeps your stories.",
    why: "Keep the stories your family tells (the campfire legend, the night the lights went out, the scarecrow that walked) before they're forgotten. Everything stays on this computer.",
    intro: "Ghostwriter is home to the Archivist, a kind ghost who writes your stories down and remembers every word.",
    plainSwitch: "Plain mode: simple words, no effects",
    howLink: "How it works",
    aboutLink: "About",
    howTitle: "How Ghostwriter works",
    how1Title: "Tell a story.",
    how1: "Speak into the microphone, upload a recording, or write it down.",
    how2Title: "The Archivist writes it down.",
    how2: "It gives the story a title and notes who, where and when, then asks what it still wonders about.",
    how3Title: "Ask the Séance.",
    how3: "Ask anything about your stories; it answers only from them and shows which ones it used.",
    howClose: "Got it, hide this",
    greeting: (n) => n === 0
      ? "The archive is empty, and so very quiet. Tell me something, my dear."
      : `Ah... you have returned. I keep ${n} of your ${n === 1 ? "memory" : "memories"}.`,
    waking: "Waking the Archivist...",
    awake: "The Archivist is awake.",
    unwell: "Something in the walls is not well. The archive may only half wake:",
    archive: "The candle wall",
    archiveHint: "Every story you give the Archivist becomes a candle. Open one to read it.",
    searchLabel: "Search titles and summaries",
    searchPlaceholder: "Search titles and summaries",
    filterLabel: "Show only memories about",
    allMemories: "every memory",
    clearFilter: "Clear filter",
    count: (shown, total) => shown === total ? `${total} ${total === 1 ? "memory" : "memories"}` : `Showing ${shown} of ${total}`,
    lighting: "Lighting the candles...",
    emptyWall: "No candles yet. The wall waits for its first memory.",
    emptyAction: "Give the Archivist its first story",
    filterEmpty: "No memory matches that.",
    legendTitle: "Each mood has its own candle and flame. Choose one to light only its candles:",
    legendItem: (mood, look) => `${mood}: ${look.shape}, ${look.flame} flame`,
    legendDim: "A dim entry has no stories with that mood yet.",
    legendDisabled: "No stories with this mood yet",
    fadeNote: "Flames burn low when you haven't opened a memory for a while. Open it to relight it.",
    lastOpened: (days) => days < 1 ? "Opened today." : `Not opened for ${days} day${days === 1 ? "" : "s"}: its flame burns low.`,
    book: "Open the memory book",
    bookHint: "Every finished story with its words, notes, answers and retellings on one page, to print or save as a PDF.",
    samplesNote: "The stories marked \"fictional sample\" were written for the demo; none of them are real memories.",
    samplesRemove: "Remove sample stories",
    removeSamplesTitle: "Remove the sample stories?",
    removeSamplesText: "The fictional demo stories leave the wall. Your own stories are not touched.",
    removeSamplesOk: "Remove them",
    samplesRemoved: (n) => `${n} sample ${n === 1 ? "story" : "stories"} removed.`,
    sample: "fictional sample",
    sampleNote: "A fictional sample story, written for the demo. It is not a real memory.",
    seance: "Séance",
    seanceHint: "Ask a question about your stories. The Archivist answers only from them, and numbers the stories it used, like this [1].",
    askPlaceholder: "What happened at Pine Lake?",
    ask: "Ask",
    askTitle: "Summon an answer from your stories",
    consulting: "The candles lean. The Archivist is searching the shelves...",
    sources: "Stories used:",
    seanceStopped: "The candles are snuffed. The séance has ended.",
    emptyQuestion: "Ask me something first, my dear: a name, a place, a time.",
    askAbout: (name) => `Ask about ${name}`,
    give: "Give the Archivist a story",
    giveHint: "Tell it out loud, in English, or upload a recording you already have. Short stories take about a minute to write down.",
    micHint: "Your browser will ask to use the microphone. The recording stays on this computer.",
    orUpload: "Or upload a recording:",
    offer: "Upload recording",
    offerTitle: "Offer it to the Archivist",
    record: "Record a story",
    recordTitle: "Speak, and the Archivist will listen",
    waitingMic: "Waiting for microphone permission (your browser is asking)...",
    recording: "Recording",
    stopSave: "Stop and keep it",
    cancelRec: "Cancel",
    oneMinuteLeft: "One minute left.",
    recDiscarded: "Discarded. Nothing was kept.",
    oneAtATime: "One recording at a time, my dear.",
    sending: "Sending it to the Archivist...",
    offering: "Offering it to the Archivist...",
    wrongType: (ext) => `The Archivist can't hear "${ext}" files. Choose a wav, mp3, m4a, webm or ogg recording.`,
    accepted: "The Archivist has your story.",
    refused: "The Archivist refused it: ",
    trouble: "The candle gutters. ",
    speak: "Let the Archivist speak",
    speakLoading: "The Archivist clears its throat...",
    speakStop: "Stop the voice",
    reaction: "The Archivist writes",
    writingNote: "The Archivist is writing its note...",
    writeNote: "Write the note now",
    unfinished: "Unfinished business",
    unfinishedHint: "What the Archivist still wonders about. Answer one, and your answer is added to this story.",
    answerRecord: "Record an answer",
    answerFile: "or upload a file",
    answerWrite: "or write it",
    answerWriteLabel: "Your answer",
    answerPlaceholder: "Write your answer here...",
    answerSubmit: "Add my answer",
    answerWorking: "Your answer is being written down...",
    addedLater: (date) => `Added later, ${date}`,
    addedTo: "Added later to",
    answerAudio: "The recording of this answer",
    removeAnswer: "Remove this answer",
    removeAnswerTitle: "Remove this answer?",
    removeAnswerText: "The answer's recording and words are removed from this story. The question stays.",
    removeAnswerOk: "Remove it",
    answerRemoved: "The answer has been removed.",
    transcript: "The words as they were spoken",
    transcriptWritten: "The words as you wrote them",
    unsure: "The Archivist wasn't sure of these words: ",
    uncertain: "The Archivist isn't sure of some words, so it left them out.",
    edited: "You corrected these words. Whisper's original words are kept too.",
    editWords: "Correct the words",
    editWordsHint: "Fix any misheard words. The Archivist can then re-read the story.",
    rereadOffer: "The words are kept. Shall the Archivist read them again, for a new title, summary, tags and questions?",
    reread: "Let the Archivist re-read it",
    notNow: "Not now",
    missing: "That memory was never given to me.",
    back: "← back to the candle wall",
    retelling: "A haunted retelling",
    retellingNote: "Told by the Archivist beside a dying fire. A retelling, not the memory itself, which stays exactly as you gave it.",
    retell: "Retell it as a ghost story",
    writingRetelling: "The Archivist is telling it anew...",
    retellAgain: "Retell it again",
    retellAgainTitle: "Tell it anew?",
    retellAgainText: "The Archivist will tell this memory again, and this telling will be replaced. Your story itself is never changed.",
    retellAgainOk: "Tell it anew",
    status: { queued: "Waiting its turn...", transcribing: "The Archivist is listening...", thinking: "The Archivist is reading...",
              noting: "The Archivist is writing its note...", failed: "The ink ran dry", unclear: "Words lost in fog" },
    stages: { transcribing: "Listening", thinking: "Reading", noting: "Writing the note" },
    stagesHint: { transcribing: "writing down your words", thinking: "title, summary, tags and questions", noting: "the Archivist's note" },
    estimate: (s) => s < 5 ? "Almost done..." : `About ${s < 90 ? `${Math.round(s / 5) * 5} seconds` : `${Math.round(s / 60)} minutes`} left.`,
    patience: "Short stories usually take about a minute. You can leave this page; the Archivist keeps working.",
    keepWorking: "You can leave this page; the Archivist keeps working.",
    fog: "The words came to me as fog...",
    fogText: "I could not make out a memory in these words, so I wrote nothing down. You can:",
    fogWhy: "Why: ",
    fogEdit: "Write down what was said",
    fogPlaceholder: "Write the story the way it was told...",
    tryAgain: "Try again",
    chooseAnother: "Choose another file",
    stopped: "Stopped. Nothing new was kept.",
    cancel: "Cancel",
    rename: "Rename",
    renameLabel: "New title",
    save: "Save",
    cancelEdit: "Cancel",
    editTags: "Edit tags",
    tagsHint: "Rename a tag to fix it. Give it the same name as another tag to merge them. Clear it to remove it. Type in an empty box to add one.",
    addTag: (label) => `Add ${label.toLowerCase()}`,
    tagLabels: { person: "People", place: "Places", era: "When", keepsake: "Keepsakes" },
    moodLabel: "Mood",
    deleteStory: "Delete this memory",
    deleteTitle: "Burn this memory?",
    deleteText: (answers) => `The recording, the words, the Archivist's note and the retelling${answers ? `, and the ${answers} ${answers === 1 ? "answer" : "answers"} added later,` : ""} will be gone. You can undo it for a few seconds.`,
    deleteOk: "Delete it",
    keepIt: "Keep it",
    deleted: "The memory has been laid to rest.",
    undo: "Undo",
    undone: "Restored.",
    tooLate: "Too late to undo.",
    aboutTitle: "About Ghostwriter",
    aboutIntro: "Ghostwriter keeps the stories your family tells. The Archivist is the ghost who lives in it: it listens, writes each story down, and answers questions about them.",
    featuresTitle: "What everything does",
    features: [
      ["Record or upload", "Speak a memory into the microphone, in English, or upload a recording."],
      ["Write it down", "Type a story instead, with spell check and autocorrect. Your draft is kept if you leave the page."],
      ["The candle wall", "Each story is a candle; its shape and flame colour show its mood. Unopened stories burn low."],
      ["Search and filter", "Find stories by words in their title or summary, or by a person, place, time or mood."],
      ["The story page", "The Archivist's note, a summary, who, where and when, the recording, and the words as spoken."],
      ["Unfinished business", "Questions the Archivist still has. Answer one and the answer joins the story."],
      ["Correct and re-read", "Fix misheard words, rename the story, edit its tags; the Archivist can read it again."],
      ["Séance", "Ask a question; the Archivist answers only from your stories and numbers its sources."],
      ["Haunted retelling", "The story retold as a campfire ghost story, with a few emojis. The original is never changed."],
      ["The Archivist's voice", "Have any note, answer or retelling read aloud."],
      ["Memory book", "Every story on one page to print, save as a PDF, or keep as a file."],
      ["Plain mode", "Simple words and no effects, for anyone who prefers them."],
    ],
    privacyTitle: "Private by design",
    privacy: "Everything runs on this computer: the speech recognition, the AI and your recordings. Nothing is sent anywhere, and the app only answers this computer (127.0.0.1).",
    toolsTitle: "The local tools it uses",
    toolState: (c) => c.ok ? "working" : c.required ? "missing" : "optional, not set up",
    close: "Close",
    badge: "Private: runs entirely on this computer",
    aboutFooter: "About and local tools",
    writeTitle: "Write a story down",
    writeHint: "No microphone, a noisy room, or a story that needs a second try? Write it here, the way you would tell it. The Archivist reads it just like a recording.",
    writeLabel: "Your story",
    writePlaceholder: "It was the last night at camp, and the fire had burned down to embers...",
    autocorrectLabel: "Autocorrect",
    writeHelp: "Misspelled words are underlined: right-click one for suggestions. Common typos are fixed as you type; press Backspace straight after a fix to undo it. Your draft is kept on this computer if you leave the page.",
    writeSubmit: "Give it to the Archivist",
    writeClear: "Clear the page",
    wordCount: (n) => n === 0 ? "" : `${n} ${n === 1 ? "word" : "words"} · about ${Math.max(1, Math.round(n / 140))} min to tell`,
    tooShort: "Write a little more, my dear: a few sentences at least.",
    handing: "Handing your pages to the Archivist...",
    fixed: (from, to) => `Autocorrect: “${from}” became “${to}”.`,
    unfixed: (from) => `Kept “${from}” as you wrote it.`,
    clearTitle: "Clear the page?",
    clearText: "Everything written here will be gone.",
    clearOk: "Clear it",
  },
  plain: {
    tagline: "A private archive for spoken family stories.",
    why: "Keep the stories your family tells (the campfire legend, the night the lights went out, the scarecrow that walked) before they're forgotten. Everything stays on this computer.",
    intro: "Ghostwriter transcribes each recording, summarises it and lets you ask questions about your stories.",
    plainSwitch: "Plain mode: simple words, no effects",
    howLink: "How it works",
    aboutLink: "About",
    howTitle: "How Ghostwriter works",
    how1Title: "Add a story.",
    how1: "Record it with the microphone, upload a recording, or type it.",
    how2Title: "It is transcribed and summarised.",
    how2: "Each story gets a title, a summary, tags and a few follow-up questions.",
    how3Title: "Ask questions.",
    how3: "Answers come only from your stories, with numbered sources.",
    howClose: "Hide this",
    greeting: (n) => `${n} ${n === 1 ? "story" : "stories"} saved.`,
    waking: "Loading the AI models...",
    awake: "Ready.",
    unwell: "Some local services are not available:",
    archive: "Stories",
    archiveHint: "Open a story to read it.",
    searchLabel: "Search titles and summaries",
    searchPlaceholder: "Search titles and summaries",
    filterLabel: "Show only stories about",
    allMemories: "All stories",
    clearFilter: "Clear filter",
    count: (shown, total) => shown === total ? `${total} ${total === 1 ? "story" : "stories"}` : `Showing ${shown} of ${total}`,
    lighting: "Loading...",
    emptyWall: "No stories yet.",
    emptyAction: "Add your first story",
    filterEmpty: "No story matches that filter.",
    legendTitle: "Colours show each story's mood. Choose one to show only those stories:",
    legendItem: (mood, look) => `${mood} (${look.flame})`,
    legendDim: "A dim entry has no stories with that mood yet.",
    legendDisabled: "No stories with this mood yet",
    fadeNote: "Stories you haven't opened for a while are shown dimmer.",
    lastOpened: (days) => days < 1 ? "Opened today." : `Last opened ${days} day${days === 1 ? "" : "s"} ago.`,
    book: "Export all stories (printable)",
    bookHint: "Every finished story with its transcript, notes, answers and retellings on one page, to print or save as a PDF.",
    samplesNote: "Stories marked \"fictional sample\" were written for the demo and are not real.",
    samplesRemove: "Remove sample stories",
    removeSamplesTitle: "Remove the sample stories?",
    removeSamplesText: "The demo stories are deleted. Your own stories are not touched.",
    removeSamplesOk: "Remove them",
    samplesRemoved: (n) => `${n} sample ${n === 1 ? "story" : "stories"} removed.`,
    sample: "fictional sample",
    sampleNote: "A fictional sample story, written for the demo. It is not real.",
    seance: "Ask your stories",
    seanceHint: "Answers come only from your stories, with numbered sources like this [1].",
    askPlaceholder: "What happened at Pine Lake?",
    ask: "Ask",
    askTitle: "Ask a question about your stories",
    consulting: "Searching your stories...",
    sources: "Sources:",
    seanceStopped: "Stopped.",
    emptyQuestion: "Type a question first.",
    askAbout: (name) => `Ask about ${name}`,
    give: "Add a story",
    giveHint: "Record it here in English, or upload a recording. Short stories take about a minute to process.",
    micHint: "Your browser will ask to use the microphone. The recording stays on this computer.",
    orUpload: "Or upload a recording:",
    offer: "Upload recording",
    offerTitle: "Upload an audio file",
    record: "Record a story",
    recordTitle: "Record with the microphone",
    waitingMic: "Waiting for microphone permission...",
    recording: "Recording",
    stopSave: "Stop and save",
    cancelRec: "Cancel",
    oneMinuteLeft: "One minute left.",
    recDiscarded: "Recording discarded.",
    oneAtATime: "One recording at a time.",
    sending: "Uploading...",
    offering: "Uploading...",
    wrongType: (ext) => `"${ext}" files are not supported. Choose a wav, mp3, m4a, webm or ogg recording.`,
    accepted: "Uploaded.",
    refused: "Upload failed: ",
    trouble: "Error: ",
    speak: "Read aloud",
    speakLoading: "Loading audio...",
    speakStop: "Stop",
    reaction: "AI note",
    writingNote: "Writing the AI note...",
    writeNote: "Write the AI note",
    unfinished: "Follow-up questions",
    unfinishedHint: "Answer one, and your answer is added to this story.",
    answerRecord: "Record an answer",
    answerFile: "or upload a file",
    answerWrite: "or type it",
    answerWriteLabel: "Answer",
    answerPlaceholder: "Type your answer...",
    answerSubmit: "Save answer",
    answerWorking: "Your answer is being processed...",
    addedLater: (date) => `Added later, ${date}`,
    addedTo: "Added later to",
    answerAudio: "The recording of this answer",
    removeAnswer: "Remove this answer",
    removeAnswerTitle: "Remove this answer?",
    removeAnswerText: "The answer's recording and transcript are removed from this story. The question stays.",
    removeAnswerOk: "Remove it",
    answerRemoved: "Answer removed.",
    transcript: "Transcript",
    transcriptWritten: "Text",
    unsure: "Low-confidence words: ",
    uncertain: "Some words were unclear and were left out of the summary.",
    edited: "Edited. The original transcript is kept too.",
    editWords: "Edit transcript",
    editWordsHint: "Fix any misheard words, then analyse the story again.",
    rereadOffer: "Saved. Analyse the edited transcript again (title, summary, tags, questions)?",
    reread: "Analyse again",
    notNow: "Not now",
    missing: "Story not found.",
    back: "← all stories",
    retelling: "Retelling",
    retellingNote: "A creative retelling written by Gemma. The original story is unchanged.",
    retell: "Write a creative retelling",
    writingRetelling: "Writing the retelling...",
    retellAgain: "Write it again",
    retellAgainTitle: "Replace the retelling?",
    retellAgainText: "A new retelling will replace this one. The story itself is not changed.",
    retellAgainOk: "Replace it",
    status: { queued: "Queued", transcribing: "Transcribing...", thinking: "Analysing...", noting: "Writing the AI note...",
              failed: "Failed", unclear: "Unclear recording" },
    stages: { transcribing: "Transcribing", thinking: "Analysing", noting: "Writing the AI note" },
    stagesHint: { transcribing: "Whisper", thinking: "Gemma", noting: "Gemma" },
    estimate: (s) => s < 5 ? "Almost done." : `About ${s < 90 ? `${Math.round(s / 5) * 5} seconds` : `${Math.round(s / 60)} minutes`} left.`,
    patience: "Short stories usually take about a minute. You can leave this page; processing continues.",
    keepWorking: "You can leave this page; processing continues.",
    fog: "This story was too unclear to process",
    fogText: "No title, summary or questions were written. You can:",
    fogWhy: "Why: ",
    fogEdit: "Type the story instead",
    fogPlaceholder: "Type the story...",
    tryAgain: "Retry",
    chooseAnother: "Choose another file",
    stopped: "Stopped.",
    cancel: "Cancel",
    rename: "Rename",
    renameLabel: "New title",
    save: "Save",
    cancelEdit: "Cancel",
    editTags: "Edit tags",
    tagsHint: "Rename a tag to fix it. Use the name of another tag to merge them. Clear it to remove it. Type in an empty box to add one.",
    addTag: (label) => `Add ${label.toLowerCase()}`,
    tagLabels: { person: "People", place: "Places", era: "When", keepsake: "Keepsakes" },
    moodLabel: "Mood",
    deleteStory: "Delete story",
    deleteTitle: "Delete this story?",
    deleteText: (answers) => `The recording, transcript, AI note and retelling${answers ? `, and ${answers} ${answers === 1 ? "answer" : "answers"},` : ""} will be deleted. You can undo it for a few seconds.`,
    deleteOk: "Delete",
    keepIt: "Cancel",
    deleted: "Story deleted.",
    undo: "Undo",
    undone: "Restored.",
    tooLate: "Too late to undo.",
    aboutTitle: "About Ghostwriter",
    aboutIntro: "Ghostwriter transcribes and organises spoken family stories, and answers questions about them. It runs entirely on this computer.",
    featuresTitle: "Features",
    features: [
      ["Record or upload", "Record with the microphone (English) or upload a recording."],
      ["Type a story", "Type or paste a story instead, with spell check and autocorrect. Drafts are saved on this computer."],
      ["Stories", "Each story is a card coloured by its mood. Stories you haven't opened for a while look dimmer."],
      ["Search and filter", "Find stories by words in their title or summary, or by a person, place, time or mood."],
      ["Story page", "An AI note, a summary, tags, the recording and the transcript."],
      ["Follow-up questions", "Answer one and the answer is added to the story."],
      ["Edit and analyse again", "Fix the transcript, rename the story or edit its tags, then analyse it again."],
      ["Questions", "Ask about your stories; answers come only from them, with numbered sources."],
      ["Retelling", "A creative retelling of a story, with a few emojis. The original is never changed."],
      ["Read aloud", "Any note, answer or retelling can be read aloud."],
      ["Export", "Every story on one printable page, or saved as a PDF or file."],
      ["Plain mode", "Simple words and no effects."],
    ],
    privacyTitle: "Privacy",
    privacy: "Everything runs on this computer: speech recognition, the AI models and your recordings. Nothing is sent anywhere, and the app only accepts connections from this computer (127.0.0.1).",
    toolsTitle: "Local tools",
    toolState: (c) => c.ok ? "working" : c.required ? "missing" : "optional, not set up",
    close: "Close",
    badge: "Private: runs entirely on this computer",
    aboutFooter: "About and local tools",
    writeTitle: "Type a story",
    writeHint: "Type or paste a story instead of recording it. It is processed the same way.",
    writeLabel: "Story text",
    writePlaceholder: "Type or paste the story here...",
    autocorrectLabel: "Autocorrect",
    writeHelp: "Misspelled words are underlined (right-click for suggestions). Common typos are corrected as you type; press Backspace right after a correction to undo it. Drafts are saved on this computer.",
    writeSubmit: "Save story",
    writeClear: "Clear",
    wordCount: (n) => n === 0 ? "" : `${n} ${n === 1 ? "word" : "words"}`,
    tooShort: "Write at least a few sentences.",
    handing: "Saving...",
    fixed: (from, to) => `Corrected “${from}” to “${to}”.`,
    unfixed: (from) => `Kept “${from}”.`,
    clearTitle: "Clear the text?",
    clearText: "The draft will be deleted.",
    clearOk: "Clear",
  },
};

const GHOST_LINES = ["Boo!", "Who disturbs my rest?", "Mind the candles, my dear.", "I remember every word you give me.",
                     "Shh... the memories are sleeping.", "Tell me a story.", "Still here. Always here."];

let plain = false;
let config = { undo_seconds: 10, max_recording_minutes: 30 };
const voice = () => COPY[plain ? "plain" : "spooky"];

// --------------------------------------------------------------------------- small helpers

const store = {
  get(key, fallback) { try { return localStorage.getItem(`ghostwriter.${key}`) ?? fallback; } catch { return fallback; } },
  set(key, value) { try { localStorage.setItem(`ghostwriter.${key}`, value); } catch { /* not essential */ } },
};

const mmss = (ms) => {
  const s = Math.max(0, Math.floor(ms / 1000));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
};
const utc = (sqliteTime) => Date.parse(sqliteTime.replace(" ", "T") + "Z");

// A ticking "0:42". One timer (in start()) updates every clock on the page.
function clock(since = Date.now()) {
  const node = el("span", { className: "elapsed", textContent: mmss(Date.now() - since) });
  node.dataset.since = since;
  return node;
}

// "Working on it" line: what is happening, how long it has taken, and a Cancel button if it can stop.
const working = (text, onCancel) => el("p", { className: "status working", role: "status" },
  `${text} `, clock(), onCancel && el("button", { type: "button", className: "link", textContent: voice().cancel, onclick: onCancel }));

// --------------------------------------------------------------------------- plain mode and copy

function applyVoice() {
  document.body.classList.toggle("plain", plain);
  const v = voice();
  document.querySelectorAll("[data-voice]").forEach((node) => { node.textContent = v[node.dataset.voice]; });
  document.querySelectorAll("[data-voice-placeholder]").forEach((node) => { node.placeholder = v[node.dataset.voicePlaceholder]; });
  document.querySelectorAll("[data-voice-title]").forEach((node) => { node.title = v[node.dataset.voiceTitle]; });
  $("#features").replaceChildren(...v.features.flatMap(([term, text]) => [el("dt", { textContent: term }), el("dd", { textContent: text })]));
  renderLegend();
  renderRecorder();
  countWords();
}

// --------------------------------------------------------------------------- health (About panel)

let voiceReady = true; // corrected by the health check; if wrong, the click explains the fix

async function loadHealth() {
  const checks = await api("/api/health");
  const v = voice();
  $("#health").replaceChildren(...checks.map((c) => el("li", { className: c.ok ? "ok" : c.required ? "bad" : "off" },
    el("strong", { textContent: `${c.name}: ` }), `${v.toolState(c)}. `, el("span", { className: "meta", textContent: c.detail }),
    !c.ok && c.fix && el("span", { className: "fix", textContent: ` Fix: ${c.fix}` }))));
  voiceReady = checks.some((c) => c.name === "Piper TTS" && c.ok);
  const broken = checks.filter((c) => c.required && !c.ok);
  const banner = $("#health-banner");
  banner.hidden = broken.length === 0;
  banner.replaceChildren(
    el("p", { textContent: v.unwell }),
    el("ul", {}, ...broken.map((c) => el("li", {},
      el("strong", { textContent: `${c.name}: ` }), `${c.detail}. `,
      c.fix && el("span", { className: "fix", textContent: `Fix: ${c.fix}` }),
    ))),
  );
}

// --------------------------------------------------------------------------- the Archivist's voice

let speaking = null; // { button, audio, done }: only one voice at a time

// Back to "Let the Archivist speak", silencing whatever was playing.
function stopSpeaking() {
  if (!speaking) return;
  speaking.audio?.pause();
  speaking.done?.();
  Object.assign(speaking.button, { textContent: voice().speak, disabled: false });
  speaking = null;
}

async function fetchPart(text, part) {
  const res = await fetch("/api/speak", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, plain, part }),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || res.statusText);
  return { blob: await res.blob(), parts: Number(res.headers.get("X-Parts")) || 1 };
}

// idle -> loading (disabled) -> playing ("Stop") -> idle when done or stopped. Text is spoken in parts:
// the first sentence starts playing while the next part is being made.
function speakButton(text) {
  if (!voiceReady) return null;
  const button = el("button", { type: "button", className: "link speak", textContent: voice().speak });
  button.onclick = async () => {
    if (speaking?.button === button) return stopSpeaking();
    stopSpeaking();
    button.parentElement.querySelector(".voice-error")?.remove();
    const me = speaking = { button, audio: null, done: null };
    Object.assign(button, { textContent: voice().speakLoading, disabled: true });
    try {
      let next = fetchPart(text, 0);
      for (let part = 0, total = 1; part < total; part += 1) {
        const { blob, parts } = await next;
        total = parts;
        if (speaking !== me) return; // stopped, or another voice started meanwhile
        if (part + 1 < total) next = fetchPart(text, part + 1);
        me.audio = new Audio(URL.createObjectURL(blob));
        Object.assign(button, { textContent: voice().speakStop, disabled: false });
        await new Promise((resolve) => { me.done = resolve; me.audio.onended = resolve; me.audio.play().catch(resolve); });
      }
      if (speaking === me) stopSpeaking();
    } catch (err) {
      if (speaking === me) stopSpeaking();
      button.after(el("p", { className: "error voice-error", textContent: voice().trouble + err.message }));
    }
  };
  return button;
}

// --------------------------------------------------------------------------- Seance

let seanceRun = null; // the question being answered, so a new one (or Cancel) can stop it

function clearSeance() {
  seanceRun?.abort();
  seanceRun = null;
  $("#seance-answer").className = ""; // drop the quill's "still writing" look
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

  let titles = new Map();
  let pen = null;
  const write = () => (pen ??= quill(answer, (id) => (titles.has(id) ? { href: `#/story/${id}`, label: titles.get(id) } : null)));
  const showError = (message) =>
    answer.replaceChildren(el("p", { className: "error", textContent: voice().trouble + message }));
  try {
    await streamEvents("/api/seance", { question, plain }, {
      sources: (data) => { titles = new Map(data.stories.map((s) => [s.id, s.title])); },
      token: (data) => write().write(data.text),
      cite: (data) => write().cite(data.id),
      error: (data) => showError(data.message),
      done: () => {
        const text = pen?.finish();
        const order = pen?.cited ?? [];
        sourcesLine.replaceChildren(...present([
          order.length > 0 && `${voice().sources} `,
          ...order.flatMap((id, i) => [
            i > 0 ? ", " : "", el("a", { href: `#/story/${id}`, textContent: `[${i + 1}] ${titles.get(id)}` }),
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

const FADE_DAYS = 30; // an unvisited candle burns down to a faint glow over about a month
const FILTER_GROUPS = [["person", "People"], ["place", "Places"], ["era", "When"], ["keepsake", "Keepsakes"]];

let allStories = []; // everything the server listed, answers included
let wallKey = ""; // skip re-rendering (and restarting the flame animations) when nothing changed

const topLevel = () => allStories.filter((s) => !s.parent_id); // answers live inside their story
const statusText = (s) => (s.status === "ready" ? s.title : voice().status[s.status] || s.status);
const daysSinceVisit = (story) => (Date.now() - utc(story.last_visited_at)) / 86_400_000;
const life = (story) => Math.min(1, Math.max(0, 1 - daysSinceVisit(story) / FADE_DAYS));
const moodOf = (s) => (s.mood in MOODS ? s.mood : FALLBACK_MOOD);
const hasMood = (mood) => topLevel().some((s) => s.status === "ready" && moodOf(s) === mood);

// A story's tags with the tags of the answers added to it, so filtering finds both.
function tagsOf(story) {
  const merged = {};
  for (const s of [story, ...allStories.filter((a) => a.parent_id === story.id)]) {
    for (const [kind, values] of Object.entries(s.entities || {})) (merged[kind] ??= []).push(...values);
  }
  return merged;
}

function candle(s, i = 0) {
  const v = voice();
  const lit = s.status === "ready";
  const meta = [localTime(s.created_at), lit && s.mood, s.is_sample && v.sample].filter(Boolean).join(" · ");
  const tooltip = [s.summary, lit && v.lastOpened(Math.floor(daysSinceVisit(s)))].filter(Boolean).join("\n");
  const node = el("a", { href: `#/story/${s.id}`, className: `candle mood-${moodOf(s)} ${lit ? "lit" : s.status}`, title: tooltip },
    el("span", { className: "art", ariaHidden: "true" },
      el("span", { className: "holder" }),
      el("span", { className: "wax" }),
      el("span", { className: "wick" }),
      el("span", { className: "flame-wrap" }, el("span", { className: "flame" })),
    ),
    el("span", { className: "label content", textContent: statusText(s) }),
    el("span", { className: "meta", textContent: meta }),
  );
  node.style.setProperty("--life", lit ? life(s).toFixed(2) : "0");
  node.style.setProperty("--i", i); // candles rise onto the wall one after another
  return node;
}

function renderLegend() {
  const v = voice();
  $("#legend").replaceChildren(...Object.entries(MOODS).map(([mood, look]) => {
    const button = el("button", { type: "button", className: `mood-${mood}` }, el("i", { ariaHidden: "true" }), v.legendItem(mood, look));
    button.dataset.mood = mood;
    return el("li", {}, button);
  }));
  syncLegend();
}

function syncLegend() {
  const filter = currentFilter();
  document.querySelectorAll("#legend button").forEach((b) => {
    const dim = !hasMood(b.dataset.mood);
    b.setAttribute("aria-pressed", String(filter === `mood:${b.dataset.mood}`));
    b.disabled = dim;
    b.title = dim ? voice().legendDisabled : "";
  });
}

function renderFilterOptions() {
  const select = $("#filter");
  const current = currentFilter();
  const groups = FILTER_GROUPS.map(([kind, label]) => {
    const values = [...new Set(topLevel().flatMap((s) => tagsOf(s)[kind] || []))].sort();
    return values.length && el("optgroup", { label },
      ...values.map((value) => el("option", { value: `${kind}:${value}`, textContent: value })));
  });
  const moods = Object.keys(MOODS).filter(hasMood);
  groups.push(moods.length > 0 && el("optgroup", { label: voice().moodLabel },
    ...moods.map((m) => el("option", { value: `mood:${m}`, textContent: m }))));
  select.replaceChildren(el("option", { value: "", textContent: voice().allMemories }), ...present(groups));
  select.value = [...select.options].some((o) => o.value === current) ? current : "";
}

// The wall's filter and search live in the address (#/?about=place:Jaipur&q=kadhi), so they survive
// a reload and the back button.
function route() {
  const hash = location.hash || "#/";
  const story = hash.match(/^#\/story\/(\d+)/);
  if (story) return { story: Number(story[1]), about: "", q: "" };
  const params = new URLSearchParams(hash.split("?")[1] || "");
  return { story: null, about: params.get("about") || "", q: params.get("q") || "" };
}

function wallAddress(about, q) {
  const params = new URLSearchParams();
  if (about) params.set("about", about);
  if (q) params.set("q", q);
  return `#/${params.size ? `?${params}` : ""}`;
}

const currentFilter = () => $("#filter").value;

function renderWall() {
  const v = voice();
  const filter = currentFilter();
  const query = $("#wall-search").value.trim().toLowerCase();
  const split = filter.indexOf(":");
  const [kind, value] = [filter.slice(0, split), filter.slice(split + 1)];
  const matchesFilter = (s) => !filter || (kind === "mood" ? s.status === "ready" && moodOf(s) === value : tagsOf(s)[kind]?.includes(value));
  const matchesQuery = (s) => !query || `${s.title || ""} ${s.summary || ""}`.toLowerCase().includes(query);
  const stories = topLevel();
  const shown = stories.filter((s) => matchesFilter(s) && matchesQuery(s));
  const empty = stories.length === 0
    ? [el("div", { className: "empty" },
        el("p", { className: "handwriting", textContent: v.emptyWall }),
        el("a", { className: "button", href: "#new-story", textContent: v.emptyAction,
                  onclick: (event) => { event.preventDefault(); $("#new-story").scrollIntoView({ behavior: "smooth" }); $("#recorder button")?.focus(); } }))]
    : [el("p", { className: "meta", textContent: v.filterEmpty })];
  $("#wall").replaceChildren(...(shown.length ? shown.map(candle) : empty));
  $("#archive").classList.toggle("is-empty", stories.length === 0); // no tools or key until there's a candle
  $("#wall-count").textContent = stories.length ? v.count(shown.length, stories.length) : "";
  $("#filter-clear").hidden = !filter && !query;
  $("#samples-row").hidden = !stories.some((s) => s.is_sample);
  syncLegend();
}

let wallRoute = null; // the filter and search the wall was last drawn for

function setWallFilter(about, q, push = true) {
  const address = wallAddress(about, q);
  if (push) location.hash = address; // the hashchange re-renders
  else { history.replaceState(null, "", address); wallRoute = `${about}
${q}`; renderWall(); }
}

// Suggested questions: the people, places and keepsakes that come up most often across the stories.
function renderChips() {
  const counts = new Map(); // lower-case name -> { name, n }
  for (const s of topLevel().filter((s) => s.status === "ready")) {
    for (const kind of ["person", "place", "keepsake"]) {
      for (const raw of tagsOf(s)[kind] || []) {
        const name = raw.replace(/\s*\(.*\)$/, "").trim(); // "Grandpa Joe (grandfather)" -> "Grandpa Joe"
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
    type: "button", className: "chip", textContent: voice().askAbout(name),
    onclick: () => {
      const question = `Tell me about ${name}.`;
      $("#seance-form").question.value = question;
      askSeance(question);
    },
  })));
}

async function loadStories() {
  const stories = await api("/api/stories");
  const ready = stories.filter((s) => s.status === "ready" && !s.parent_id).length;
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
}

// --------------------------------------------------------------------------- recording

let recording = null; // the one recording in progress: { cancelled, session, timer }

// The record button and everything it turns into: waiting for permission, recording (clock, level,
// Stop, Cancel), sending. `answersQuestionId` records an answer to that question instead of a story.
function recorderPanel({ answersQuestionId = null, primary = false } = {}) {
  const box = el("div", { className: "rec" });
  const idle = (note = null) => {
    const v = voice();
    const label = answersQuestionId ? v.answerRecord : v.record;
    box.replaceChildren(...present([
      el("button", { type: "button", className: primary ? "record" : "secondary", textContent: label, title: v.recordTitle, onclick: start }),
      note,
    ]));
  };

  async function start() {
    const v = voice();
    if (recording) return idle(el("p", { className: "meta", textContent: v.oneAtATime }));
    const me = recording = { cancelled: false, session: null, timer: null };
    box.replaceChildren(el("p", { className: "status", role: "status", textContent: v.waitingMic }),
      el("button", { type: "button", className: "link", textContent: v.cancelRec, onclick: () => {
        me.cancelled = true;
        recording = null;
        idle();
      } }));
    try {
      me.session = await startRecording();
    } catch (err) {
      if (recording === me) recording = null;
      if (me.cancelled) return;
      const problem = micProblem(err);
      return idle(el("p", { className: "error", role: "alert", textContent: plain ? problem.fix : `${problem.ghost} ${problem.fix}` }));
    }
    if (me.cancelled) return me.session.cancel();

    const started = Date.now();
    const limit = config.max_recording_minutes * 60_000;
    const time = el("span", { className: "elapsed", textContent: "0:00" });
    const bar = el("i");
    const warning = el("span", { className: "warn" });
    box.replaceChildren(
      el("p", { className: "recording", role: "status" }, el("span", { className: "dot", ariaHidden: "true" }),
        `${v.recording} `, time, " ", el("span", { className: "meter", ariaHidden: "true" }, bar), " ", warning),
      el("div", { className: "row" },
        el("button", { type: "button", textContent: v.stopSave, onclick: () => finish(true) }),
        el("button", { type: "button", className: "link", textContent: v.cancelRec, onclick: () => finish(false) })));
    me.timer = setInterval(() => {
      const ms = Date.now() - started;
      time.textContent = mmss(ms);
      bar.style.transform = `scaleX(${me.session.level().toFixed(2)})`;
      if (ms >= limit - 60_000) warning.textContent = v.oneMinuteLeft;
      if (ms >= limit) finish(true);
    }, 150);

    async function finish(keep) {
      if (recording !== me) return;
      clearInterval(me.timer);
      recording = null;
      if (!keep) {
        me.session.cancel();
        return idle(el("p", { className: "meta", textContent: voice().recDiscarded }));
      }
      box.replaceChildren(el("p", { className: "status", role: "status", textContent: voice().sending }));
      const file = await me.session.stop();
      await upload(file, { answersQuestionId, status: box, after: idle });
    }
  }

  idle();
  return box;
}

function renderRecorder() {
  if (!recording) $("#recorder").replaceChildren(recorderPanel({ primary: true }));
}

// --------------------------------------------------------------------------- uploads

// Send a recording. Problems are shown where the visitor is looking (`status`), and nothing is
// saved for a file that isn't a usable recording.
async function upload(file, { answersQuestionId = null, status, form = null, after = null, replacing = null }) {
  const v = voice();
  const ext = (file.name.match(/\.[^.]+$/)?.[0] || "").toLowerCase();
  const showError = (message) => {
    status.replaceChildren(el("p", { className: "error", role: "alert", textContent: message }));
    after?.(status.firstChild);
  };
  if (!AUDIO_EXTENSIONS.includes(ext)) return showError(v.wrongType(ext || file.name));
  const data = new FormData();
  data.append("file", file);
  if (answersQuestionId) data.append("answers_question_id", answersQuestionId);
  const button = form?.querySelector("button");
  status.replaceChildren(el("p", { className: "status", role: "status", textContent: v.offering }));
  if (button) button.disabled = true;
  try {
    const { id } = await api("/api/stories", { method: "POST", body: data });
    form?.reset();
    if (replacing) await send(`/api/stories/${replacing}`, "DELETE").catch(() => null);
    if (after) after(); // a recorder: back to its button
    else {
      status.replaceChildren(el("p", { className: "meta", textContent: v.accepted }));
      setTimeout(() => status.replaceChildren(), 8000);
    }
    if (answersQuestionId) refresh(true); // the answer is shown inside the story being read
    else location.hash = `#/story/${id}`;
  } catch (err) {
    showError(v.refused + err.message);
  } finally {
    if (button) button.disabled = false;
  }
}

// --------------------------------------------------------------------------- written stories

const wordsIn = (text) => text.trim().split(/\s+/).filter(Boolean).length;

// Give typed words to the Archivist (a story, or an answer to `answersQuestionId`). Returns the new id.
async function sendWritten(text, answersQuestionId = null) {
  const { id } = await send("/api/stories/written", "POST", { text, answers_question_id: answersQuestionId });
  return id;
}

function countWords() {
  const box = $("#write-text");
  if (box) $("#write-count").textContent = voice().wordCount(wordsIn(box.value));
}

// The "Write a story down" page: autocorrect (switchable, remembered), a word count, and a draft that
// survives leaving the page. Sending it opens the new story, like a recording does.
function setUpWriting() {
  const box = $("#write-text");
  const form = $("#write-form");
  const status = $("#write-status");
  const toggle = $("#autocorrect-toggle");
  const note = $("#write-fixed");
  let hideNote = null;
  toggle.checked = store.get("autocorrect", "1") === "1";
  toggle.addEventListener("change", () => store.set("autocorrect", toggle.checked ? "1" : "0"));
  attachAutocorrect(box, { enabled: () => toggle.checked, onFix: (from, to, undone) => {
    note.textContent = undone ? voice().unfixed(from) : voice().fixed(from, to);
    clearTimeout(hideNote);
    hideNote = setTimeout(() => { note.textContent = ""; }, 4000);
  } });
  box.value = store.get("draft", "");
  countWords();
  box.addEventListener("input", () => {
    store.set("draft", box.value);
    countWords();
    status.replaceChildren();
  });
  $("#write-clear").addEventListener("click", async () => {
    const v = voice();
    if (box.value.trim() && !await confirmDialog({ title: v.clearTitle, text: v.clearText, ok: v.clearOk, cancel: v.keepIt })) return;
    box.value = "";
    store.set("draft", "");
    countWords();
    box.focus();
  });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const v = voice();
    const text = box.value.trim();
    if (wordsIn(text) < 8) {
      status.replaceChildren(el("p", { className: "error", role: "alert", textContent: v.tooShort }));
      return box.focus();
    }
    const button = form.querySelector("button[type=submit]");
    button.disabled = true;
    status.replaceChildren(el("p", { className: "status", textContent: v.handing }));
    try {
      const id = await sendWritten(text);
      box.value = "";
      store.set("draft", "");
      countWords();
      status.replaceChildren();
      location.hash = `#/story/${id}`;
    } catch (err) {
      status.replaceChildren(el("p", { className: "error", role: "alert", textContent: v.refused + err.message }));
    } finally {
      button.disabled = false;
    }
  });
}

// --------------------------------------------------------------------------- story page

const written = new Map(); // "reaction:3" -> finished text, so re-renders never re-ask Gemma

// Something Gemma writes once per story (the reaction, the retelling): replayed if already
// written, otherwise streamed in, either straight away or when the visitor asks for it.
function writtenBlock(story, kind, { heading, note, startNow }) {
  const key = `${kind}:${story.id}`;
  const v = voice();
  const box = el("div", { className: `${kind} content` });
  const tools = el("div", { className: "tools" }); // speak, retell again, or the working line
  const wrap = el("section", { className: `${kind}-section` }, el("h3", { textContent: heading }),
    note && el("p", { className: "meta", textContent: note }), box, tools);
  const startLabel = kind === "retelling" ? v.retell : v.writeNote;
  const show = (text) => {
    written.set(key, text);
    box.className = `${kind} content`; // drop the quill's "still writing" look
    box.replaceChildren(el("p", { className: "ghost-text", textContent: text }));
    tools.replaceChildren(...present([speakButton(text), kind === "retelling" && el("button", {
      type: "button", className: "link", textContent: v.retellAgain,
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
    if (before) show(before); else { box.className = `${kind} content`; box.replaceChildren(); offer(); }
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

const STAGES = ["transcribing", "thinking", "noting"];
const firstSeen = new Map(); // story id -> when this page first saw it waiting (before the server started it)
const editable = (s) => ["ready", "failed", "unclear"].includes(s.status);

// Which step the Archivist is on, for how long, and about how long is left. A step list, not buttons.
function progress(s) {
  const v = voice();
  const stages = STAGES.filter((stage) => !(s.written && stage === "transcribing") && !(s.answers_question_id && stage === "noting"));
  const now = stages.indexOf(s.status);
  const done = (stage, i) => i < now || (stage === "transcribing" && Boolean(s.transcript));
  if (!firstSeen.has(s.id)) firstSeen.set(s.id, Date.now());
  const since = s.started_at && s.status !== "queued" ? utc(s.started_at) : firstSeen.get(s.id);
  return el("div", { className: "progress", role: "status" },
    el("ol", { className: "stages" }, ...stages.map((stage, i) => {
      const item = el("li", { className: done(stage, i) ? "done" : i === now ? "now" : "" },
        el("span", { className: "step-name", textContent: v.stages[stage] }),
        el("span", { className: "step-hint", textContent: v.stagesHint[stage] }));
      if (i === now) item.setAttribute("aria-current", "step");
      return item;
    })),
    el("p", { className: "status" }, `${v.status[s.status]} `, clock(since)),
    el("p", { className: "meta", textContent: s.estimate_s == null ? v.patience : `${v.estimate(s.estimate_s)} ${v.keepWorking}` }),
  );
}

// The title, with a Rename button that swaps it for a small form.
function titleRow(s) {
  const v = voice();
  const heading = el("h2", { tabIndex: -1, className: "content", textContent: statusText(s) });
  if (s.status !== "ready" || !s.title) return heading;
  const row = el("div", { className: "title-row" }, heading);
  row.append(el("button", { type: "button", className: "link", textContent: v.rename, onclick: () => {
    const input = el("input", { type: "text", value: s.title, maxLength: 120, required: true, ariaLabel: v.renameLabel });
    const form = el("form", { className: "inline-edit editing" }, input,
      el("button", { type: "submit", textContent: v.save }),
      el("button", { type: "button", className: "link", textContent: v.cancelEdit, onclick: () => form.replaceWith(row) }));
    form.onsubmit = (event) => {
      event.preventDefault();
      input.value = input.value.trim(); // only spaces counts as empty: the browser says it's required
      if (!input.reportValidity()) return;
      saveStory(s.id, { title: input.value }, form);
    };
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
    near.append(el("p", { className: "error", role: "alert", textContent: voice().trouble + err.message }));
  }
}

const TAG_KINDS = ["person", "place", "era", "keepsake"];

// People, places, eras, keepsakes and mood, with an editor to add, rename, merge or remove them.
function tagsBlock(s) {
  const v = voice();
  const e = s.entities || {};
  const rows = TAG_KINDS.filter((kind) => e[kind]?.length).flatMap((kind) =>
    [el("dt", { textContent: v.tagLabels[kind] }), el("dd", { className: "content", textContent: e[kind].join(", ") })]);
  if (s.mood) rows.push(el("dt", { textContent: v.moodLabel }), el("dd", { textContent: s.mood }));
  const list = el("dl", { className: "details" }, ...rows);
  if (s.status !== "ready") return list;
  const wrap = el("div", { className: "tags" }, list);
  wrap.append(el("button", { type: "button", className: "link", textContent: v.editTags, onclick: () => {
    const fields = [];
    const mood = el("select", { ariaLabel: v.moodLabel },
      ...Object.keys(MOODS).map((m) => el("option", { value: m, textContent: m })));
    mood.value = moodOf(s);
    const form = el("form", { className: "tags-edit editing" },
      el("p", { className: "meta", textContent: v.tagsHint }),
      ...TAG_KINDS.map((kind) => {
        const label = v.tagLabels[kind];
        const inputs = (e[kind] || []).map((value) => {
          const input = el("input", { type: "text", value, maxLength: 80, ariaLabel: `${label}: ${value}` });
          fields.push({ kind, old: value, input });
          return input;
        });
        const add = el("input", { type: "text", maxLength: 80, placeholder: v.addTag(label), ariaLabel: v.addTag(label) });
        fields.push({ kind, old: "", input: add });
        return el("fieldset", {}, el("legend", { textContent: label }), ...inputs, add);
      }),
      el("label", { className: "mood-pick" }, `${v.moodLabel} `, mood),
      el("div", { className: "row" },
        el("button", { type: "submit", textContent: v.save }),
        el("button", { type: "button", className: "link", textContent: v.cancelEdit, onclick: () => form.replaceWith(wrap) })));
    form.onsubmit = async (event) => {
      event.preventDefault();
      form.querySelector(".error")?.remove();
      try {
        for (const { kind, old, input } of fields) {
          const value = input.value.trim();
          if (value !== old && (old || value)) await send(`/api/stories/${s.id}/tags`, "POST", { kind, old, new: value });
        }
        if (mood.value !== s.mood) await send(`/api/stories/${s.id}`, "PATCH", { mood: mood.value });
        await refresh(true);
      } catch (err) {
        form.append(el("p", { className: "error", role: "alert", textContent: v.trouble + err.message }));
      }
    };
    wrap.replaceWith(form);
    fields[0].input.focus();
  } }));
  return wrap;
}

// "The words as they were spoken" (or written), with an editor; saving offers to let Gemma read them
// again. For a recording lost in fog the editor starts empty: the visitor writes down what was said.
function transcriptBlock(s) {
  const v = voice();
  const quality = s.quality ? JSON.parse(s.quality) : null;
  const details = el("details", { className: "words", id: `words-${s.id}` },
    el("summary", {}, s.written ? v.transcriptWritten : v.transcript),
    el("p", { className: "transcript content", textContent: s.transcript }));
  if (quality?.low_words?.length && s.status === "ready") {
    details.append(el("p", { className: "meta" }, v.unsure, el("span", { className: "content", textContent: quality.low_words.slice(0, 8).join(", ") })));
  }
  if (s.transcript_original) details.append(el("p", { className: "meta", textContent: v.edited }));
  if (!editable(s)) return details;
  const tools = el("div", { className: "row" });
  tools.append(el("button", { type: "button", className: "link edit-words", textContent: v.editWords, onclick: () => {
    const fog = s.status === "unclear";
    const box = storyBox({ value: fog ? "" : s.transcript, rows: fog ? 10 : 8, required: true, ariaLabel: v.transcript,
                           placeholder: fog ? v.fogPlaceholder : "" });
    attachAutocorrect(box);
    const form = el("form", { className: "transcript-edit editing" }, box,
      el("div", { className: "row" },
        el("button", { type: "submit", textContent: v.save }),
        el("button", { type: "button", className: "link", textContent: v.cancelEdit, onclick: () => refresh(true) })));
    form.onsubmit = async (event) => {
      event.preventDefault();
      form.querySelector(".error")?.remove();
      box.value = box.value.trim();
      if (!box.reportValidity()) return;
      try {
        await send(`/api/stories/${s.id}`, "PATCH", { transcript: box.value });
        if (fog) return reread(s.id); // written down instead: read it straight away
        form.replaceWith(el("div", { className: "reread editing", role: "status" },
          el("p", { textContent: v.rereadOffer }),
          el("button", { type: "button", textContent: v.reread, onclick: () => reread(s.id) }), " ",
          el("button", { type: "button", className: "link", textContent: v.notNow, onclick: () => refresh(true) })));
      } catch (err) {
        form.append(el("p", { className: "error", role: "alert", textContent: v.trouble + err.message }));
      }
    };
    tools.replaceWith(form);
    details.open = true;
    box.focus();
  } }), el("span", { className: "meta", textContent: v.editWordsHint }));
  details.append(tools);
  return details;
}

// An answer recorded later, shown inside the story under its question.
function addedLater(answer) {
  const v = voice();
  if (IN_PROGRESS.includes(answer.status)) {
    return el("div", { className: "added" }, el("p", { className: "status", role: "status" },
      `${v.answerWorking} (${v.stages[answer.status] || v.status.queued}) `,
      clock(answer.started_at && answer.status !== "queued" ? utc(answer.started_at) : Date.now())));
  }
  const remove = el("button", { type: "button", className: "link", textContent: v.removeAnswer, onclick: async () => {
    if (!await confirmDialog({ title: v.removeAnswerTitle, text: v.removeAnswerText, ok: v.removeAnswerOk, cancel: v.keepIt })) return;
    await deleteWithUndo(answer.id, v.answerRemoved, false);
  } });
  if (answer.status !== "ready") {
    return el("div", { className: "added" },
      el("p", { className: "error", textContent: answer.status === "unclear" ? v.fog : answer.error }), remove);
  }
  return el("div", { className: "added" },
    el("p", { className: "meta", textContent: v.addedLater(localTime(answer.created_at)) }),
    el("p", { className: "content", textContent: answer.summary }),
    answer.audio_original && el("audio", { controls: true, preload: "metadata", src: `/api/stories/${answer.id}/audio`, ariaLabel: v.answerAudio }),
    el("details", {}, el("summary", {}, answer.written ? v.transcriptWritten : v.transcript),
      el("p", { className: "transcript content", textContent: answer.transcript })),
    remove);
}

function questionItem(q) {
  const v = voice();
  if (q.answer) return el("li", {}, el("span", { className: "content", textContent: q.text }), addedLater(q.answer));
  const picker = el("input", { type: "file", accept: AUDIO_TYPES, hidden: true });
  const status = el("div", { className: "answer-status" });
  picker.onchange = () => picker.files[0] && upload(picker.files[0], { answersQuestionId: q.id, status });
  const writeIt = () => {
    const box = storyBox({ rows: 4, required: true, ariaLabel: v.answerWriteLabel, placeholder: v.answerPlaceholder, maxLength: 20000 });
    attachAutocorrect(box);
    const form = el("form", { className: "answer-write editing" }, box,
      el("div", { className: "row" },
        el("button", { type: "submit", textContent: v.answerSubmit }),
        el("button", { type: "button", className: "link", textContent: v.cancelEdit, onclick: () => form.remove() })));
    form.onsubmit = async (event) => {
      event.preventDefault();
      form.querySelector(".error")?.remove();
      if (wordsIn(box.value) < 3) {
        form.append(el("p", { className: "error", role: "alert", textContent: voice().tooShort }));
        return box.focus();
      }
      const button = form.querySelector("button[type=submit]");
      button.disabled = true; // one answer per click, however fast the clicks
      try {
        await sendWritten(box.value.trim(), q.id);
        form.remove();
        refresh(true);
      } catch (err) {
        form.append(el("p", { className: "error", role: "alert", textContent: voice().refused + err.message }));
        button.disabled = false;
      }
    };
    status.replaceChildren(form);
    box.focus();
  };
  return el("li", {}, el("span", { className: "content", textContent: q.text }),
    el("div", { className: "answer-tools" }, recorderPanel({ answersQuestionId: q.id }),
      el("button", { type: "button", className: "link", textContent: v.answerFile, onclick: () => picker.click() }), picker,
      el("button", { type: "button", className: "link", textContent: v.answerWrite, onclick: writeIt })),
    status);
}

function unfinishedBlock(s) {
  const v = voice();
  if (s.questions.length === 0 || s.status !== "ready") return null;
  return el("section", { className: "unfinished" },
    el("h3", { textContent: v.unfinished }),
    el("p", { className: "hint", textContent: v.unfinishedHint }),
    el("ul", { className: "questions" }, ...s.questions.map(questionItem)));
}

// Whisper couldn't make out the words: nothing was invented. Say so, and offer the ways forward.
function fogBlock(s) {
  const v = voice();
  const quality = s.quality ? JSON.parse(s.quality) : { reasons: [] };
  return el("section", { className: "fog-box", role: "status" },
    el("h3", { className: "handwriting", textContent: v.fog }),
    el("p", { textContent: v.fogText }),
    el("ul", { className: "fog-actions" },
      el("li", {}, el("button", { type: "button", className: "secondary", textContent: v.fogEdit, onclick: () => {
        const words = $(`#words-${s.id}`);
        words.open = true;
        words.querySelector(".edit-words")?.click();
        words.scrollIntoView({ block: "center" });
      } })),
      el("li", {}, deleteButton(s, true))),
    quality.reasons?.length > 0 && el("p", { className: "meta", textContent: v.fogWhy + quality.reasons.join("; ") + "." }));
}

// A failure: try again if it might pass, otherwise another file (or delete).
function failedBlock(s) {
  const v = voice();
  const picker = el("input", { type: "file", accept: AUDIO_TYPES, hidden: true });
  const status = el("div");
  picker.onchange = () => picker.files[0] && upload(picker.files[0], { answersQuestionId: s.answers_question_id, status, replacing: s.id });
  return el("section", { className: "failed-box", role: "alert" },
    el("p", { className: "error", textContent: s.error }),
    el("div", { className: "row" }, ...present([
      s.error_kind !== "audio" && el("button", { type: "button", textContent: v.tryAgain, onclick: () => retry(s.id) }),
      s.error_kind === "audio" && el("button", { type: "button", textContent: v.chooseAnother, onclick: () => picker.click() }),
      picker,
    ])),
    status);
}

function deleteButton(s, inline = false) {
  const v = voice();
  return editable(s) && el("button", { type: "button", className: inline ? "danger inline" : "danger", textContent: v.deleteStory, onclick: async () => {
    const answers = s.questions.filter((q) => q.answer).length;
    if (!await confirmDialog({ title: v.deleteTitle, text: v.deleteText(answers), ok: v.deleteOk, cancel: v.keepIt })) return;
    await deleteWithUndo(s.id, v.deleted, true);
  } });
}

// Delete now, with an Undo in the notice for as long as the server keeps it.
async function deleteWithUndo(id, message, leave) {
  const v = voice();
  try {
    await send(`/api/stories/${id}`, "DELETE");
  } catch (err) {
    return toast(v.trouble + err.message);
  }
  // A story added later may reuse this id once it is purged: forget its note, retelling and clock.
  written.delete(`reaction:${id}`);
  written.delete(`retelling:${id}`);
  firstSeen.delete(id);
  toast(message, { label: v.undo, run: async () => {
    try {
      await api(`/api/stories/${id}/restore`, { method: "POST" });
      toast(v.undone);
      if (leave) location.hash = `#/story/${id}`;
      else refresh(true);
    } catch {
      toast(v.tooLate);
    }
  } }, config.undo_seconds * 1000);
  if (leave) {
    leftByDeleting = true;
    location.hash = "#/";
  } else {
    refresh(true);
  }
}

function renderStory(s) {
  const v = voice();
  return present([
    el("a", { href: "#/", className: "meta back", textContent: v.back }),
    titleRow(s),
    IN_PROGRESS.includes(s.status) && progress(s),
    s.status === "unclear" && fogBlock(s),
    s.status === "failed" && failedBlock(s),
    Boolean(s.is_sample) && el("p", { className: "meta", textContent: v.sampleNote }),
    s.answers && el("p", { className: "meta" }, `${v.addedTo}: `,
      el("a", { href: `#/story/${s.answers.story_id}`, textContent: s.answers.story_title || s.answers.text })),
    s.status === "ready" && !s.answers_question_id && writtenBlock(s, "reaction", { heading: v.reaction, startNow: true }),
    s.summary && el("p", { className: "summary content", textContent: s.summary }),
    Boolean(s.uncertain) && el("p", { className: "meta uncertain", textContent: v.uncertain }),
    s.audio_original && el("audio", { controls: true, preload: "metadata", src: `/api/stories/${s.id}/audio`, ariaLabel: v.transcript }),
    tagsBlock(s),
    unfinishedBlock(s),
    s.status === "ready" && !s.answers_question_id && writtenBlock(s, "retelling", { heading: v.retelling, note: v.retellingNote, startNow: false }),
    s.transcript && transcriptBlock(s),
    s.status !== "unclear" && deleteButton(s),
  ]);
}

let shown = { id: null, busy: false }; // the story on screen, and whether it (or an answer) is being processed
let leftByDeleting = false;

// Don't redraw a story under the visitor's hands: while they record, edit or a dialog is open.
const storyLocked = () => Boolean(recording) || Boolean(document.querySelector("#story .editing")) || $("#confirm").open;

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

const isBusy = (s) => Boolean(s) && (IN_PROGRESS.includes(s.status) || s.questions.some((q) => q.answer && IN_PROGRESS.includes(q.answer.status)));

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
function toast(text, action = null, ms = 5000) {
  const node = $("#toast");
  const hide = () => { node.hidden = true; };
  node.replaceChildren(el("span", { textContent: text }),
    ...present([action && el("button", { type: "button", className: "link", textContent: action.label,
      onclick: () => { hide(); action.run(); } })]));
  node.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(hide, ms);
}

// --------------------------------------------------------------------------- actions

async function retry(id) {
  await api(`/api/stories/${id}/retry`, { method: "POST" }).catch((err) => toast(voice().trouble + err.message));
  refresh(true);
}

async function reread(id) {
  try {
    await api(`/api/stories/${id}/reread`, { method: "POST" });
    written.delete(`reaction:${id}`); // the note is rewritten for the new words
    firstSeen.delete(id);
  } catch (err) {
    toast(voice().trouble + err.message);
  }
  await refresh(true);
  $("#story .progress")?.scrollIntoView({ block: "center" }); // the visitor may be far down the page
}

// The home page (candle wall, Seance, new story) and a story are separate views. Opening a story
// starts at its top; going back returns to where you were on the wall.
let homeScroll = 0;
addEventListener("scroll", () => { if (!document.body.classList.contains("reading")) homeScroll = scrollY; }, { passive: true });

// Re-render the list (and the open story if it may have changed); poll while anything is processing.
let pollTimer = null;
async function refresh(force = false) {
  clearTimeout(pollTimer);
  const stories = await loadStories();
  const r = route();
  if (r.story === null) {
    if (document.body.classList.contains("reading")) { // leaving a story
      const left = shown.id;
      stopSpeaking(); // leaving a story silences its voice
      document.body.classList.remove("reading");
      $("#story").hidden = true;
      $("#story").replaceChildren(); // nothing of it stays behind, for screen readers or scripts
      window.scrollTo(0, leftByDeleting ? 0 : homeScroll);
      if (!leftByDeleting) document.querySelector(`.candle[href="#/story/${left}"]`)?.focus({ preventScroll: true });
      leftByDeleting = false;
    }
    if (`${r.about}
${r.q}` !== wallRoute) { // the dropdown has already changed, so compare with what was drawn
      wallRoute = `${r.about}
${r.q}`;
      $("#filter").value = r.about;
      $("#wall-search").value = r.q;
      renderWall();
    }
    shown = { id: null, busy: false };
  } else if (force || r.story !== shown.id || (shown.busy && !storyLocked())) {
    const isNew = r.story !== shown.id;
    document.body.classList.add("reading");
    const story = await showStory(r.story);
    shown = { id: r.story, busy: isBusy(story) };
    if (isNew) {
      window.scrollTo(0, 0);
      $("#story h2")?.focus({ preventScroll: true }); // keyboard and screen-reader users land on the title
      if (story) relight(r.story);
    }
  }
  if (stories.some((s) => IN_PROGRESS.includes(s.status))) pollTimer = setTimeout(refresh, 2000);
}

// --------------------------------------------------------------------------- whispers

// Sometimes (not always) the Archivist murmurs a line from a faded story when the page opens.
// It floats over the corner of the page, so nothing moves, and says which story it came from.
async function maybeWhisper() {
  if (plain || Math.random() > 0.7) return;
  const res = await fetch("/api/whisper");
  if (res.status !== 200) return;
  const w = await res.json();
  const node = $("#whisper");
  node.replaceChildren(el("p", { className: "content", textContent: `“${w.text}”` }),
    el("p", { className: "from" }, "— from ", el("a", { href: `#/story/${w.story_id}`, textContent: w.title })),
    el("button", { type: "button", className: "link close", ariaLabel: "Close", textContent: "×", onclick: () => { node.hidden = true; } }));
  node.hidden = false;
  setTimeout(() => node.classList.add("fading"), 14000);
  setTimeout(() => { node.hidden = true; node.classList.remove("fading"); }, 18000);
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
  // Poke the ghost: it wobbles (unless motion is reduced) and says something. The bubble is shown
  // and hidden by a timer, not an animation, so it appears with reduced motion too.
  const ghost = $("#mascot");
  const bubble = $("#ghost-says");
  let hide = null;
  ghost.addEventListener("click", () => {
    const lines = GHOST_LINES.filter((line) => line !== bubble.textContent);
    bubble.textContent = lines[Math.floor(Math.random() * lines.length)];
    bubble.hidden = false;
    ghost.classList.remove("boo");
    void ghost.offsetWidth; // restart the wobble on every poke
    ghost.classList.add("boo");
    clearTimeout(hide);
    hide = setTimeout(() => { bubble.hidden = true; }, 2800);
  });
}

// --------------------------------------------------------------------------- start

async function wake() {
  const note = $("#wake");
  const say = (key) => { // through data-voice, so switching plain mode mid-way changes the words too
    if (key) { note.dataset.voice = key; note.textContent = voice()[key]; } else { delete note.dataset.voice; note.textContent = ""; }
  };
  say("waking");
  try {
    await fetch("/api/warm", { method: "POST" }); // returns once Gemma and Whisper are loaded
    say("awake");
    setTimeout(() => say(null), 4000);
  } catch {
    say(null);
  }
}

async function start() {
  const defaults = await api("/api/settings").catch(() => ({}));
  config = { ...config, ...defaults };
  if (defaults.moods && defaults.moods.join() !== Object.keys(MOODS).join()) console.warn("mood lists differ", defaults.moods);
  plain = store.get("plain", defaults.plain_mode_default ? "1" : "0") === "1";
  $("#plain-toggle").checked = plain;
  applyVoice();

  $("#plain-toggle").addEventListener("change", (event) => {
    plain = event.target.checked;
    store.set("plain", plain ? "1" : "0");
    $("#toast").hidden = true; // a notice in the other voice
    wallKey = "";
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
  $("#filter").addEventListener("change", () => setWallFilter(currentFilter(), $("#wall-search").value.trim()));
  $("#wall-search").addEventListener("input", () => setWallFilter(currentFilter(), $("#wall-search").value.trim(), false));
  $("#filter-clear").addEventListener("click", () => setWallFilter("", ""));
  $("#legend").addEventListener("click", (event) => {
    const mood = event.target.closest("button")?.dataset.mood;
    if (!mood) return;
    setWallFilter(currentFilter() === `mood:${mood}` ? "" : `mood:${mood}`, $("#wall-search").value.trim()); // a second click shows every candle
  });
  $("#upload-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const file = event.target.file.files[0];
    if (file) upload(file, { status: $("#upload-status"), form: event.target });
  });
  $("#upload-form").file.addEventListener("change", () => $("#upload-status").replaceChildren());
  setUpWriting();
  $("#samples-remove").addEventListener("click", async () => {
    const v = voice();
    if (!await confirmDialog({ title: v.removeSamplesTitle, text: v.removeSamplesText, ok: v.removeSamplesOk, cancel: v.keepIt })) return;
    const { removed } = await send("/api/samples", "DELETE").catch(() => ({ removed: 0 }));
    toast(v.samplesRemoved(removed));
    refresh(true);
  });
  window.addEventListener("hashchange", () => refresh());
  haunt();
  setInterval(() => document.querySelectorAll(".elapsed[data-since]").forEach((node) => {
    node.textContent = mmss(Date.now() - Number(node.dataset.since));
  }), 1000);

  // The "how it works" guide, until the visitor hides it (remembered); the header link brings it back.
  $("#how").hidden = store.get("howHidden", "0") === "1";
  $("#how-close").addEventListener("click", () => { $("#how").hidden = true; store.set("howHidden", "1"); });
  $("#how-open").addEventListener("click", async () => {
    $("#how").hidden = false;
    store.set("howHidden", "0");
    if (route().story !== null) {
      location.hash = "#/";
      await refresh();
    }
    $("#how").scrollIntoView({ block: "center" });
    $("#how-close").focus({ preventScroll: true });
  });
  const openAbout = () => { loadHealth().catch(() => {}); $("#about").showModal(); };
  $("#about-open").addEventListener("click", openAbout);
  $("#about-open-footer").addEventListener("click", openAbout);

  wake();
  loadHealth().catch(() => {});
  await refresh();
  setTimeout(() => maybeWhisper().catch(() => {}), 2500);
}

start();
