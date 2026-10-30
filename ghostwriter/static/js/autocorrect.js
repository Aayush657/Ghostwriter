// Autocorrect for the "write a story" boxes, fully offline. The browser's own spell check underlines
// unknown words (right-click for suggestions); this fixes common typos and missing apostrophes as
// you type, the way a phone keyboard does. Backspace straight after a fix puts your word back, and
// Ctrl+Z undoes it too.

// Typos people make all the time, and words a phone would fix. Only unambiguous ones: never a real
// word ("wont", "were", "its", "ill" and "lets" are left alone).
const FIXES = {
  // apostrophes
  dont: "don't", cant: "can't", didnt: "didn't", doesnt: "doesn't", isnt: "isn't", wasnt: "wasn't",
  werent: "weren't", arent: "aren't", couldnt: "couldn't", wouldnt: "wouldn't", shouldnt: "shouldn't",
  havent: "haven't", hasnt: "hasn't", hadnt: "hadn't", mustnt: "mustn't", neednt: "needn't",
  im: "I'm", ive: "I've", youre: "you're", youve: "you've", theyre: "they're", theyve: "they've",
  thats: "that's", whats: "what's", theres: "there's", heres: "here's", wheres: "where's", whos: "who's",
  hows: "how's", wouldve: "would've", couldve: "could've", shouldve: "should've", mightve: "might've",
  i: "I", "i'm": "I'm", "i've": "I've", "i'd": "I'd", "i'll": "I'll", dosent: "doesn't",
  // swapped and missing letters
  teh: "the", hte: "the", adn: "and", nad: "and", taht: "that", thta: "that", waht: "what", wiht: "with",
  whith: "with", wihch: "which", wich: "which", woudl: "would", yuo: "you", jsut: "just", knwo: "know",
  konw: "know", abotu: "about", aroudn: "around", agian: "again", alwasy: "always", allways: "always",
  befor: "before", becuase: "because", becasue: "because", beacuse: "because", frist: "first",
  thier: "their", theif: "thief", freind: "friend", freinds: "friends", beleive: "believe",
  beleived: "believed", recieve: "receive", recieved: "received", decieve: "deceive", peice: "piece",
  neice: "niece", wierd: "weird", wierdly: "weirdly", cheif: "chief", feild: "field", feilds: "fields",
  untill: "until", realy: "really", finaly: "finally", basicly: "basically", usally: "usually",
  probaly: "probably", probobly: "probably", definately: "definitely", seperate: "separate",
  seperated: "separated", occured: "occurred", ocurred: "occurred", begining: "beginning",
  beggining: "beginning", tommorow: "tomorrow", tomorow: "tomorrow", accross: "across", alot: "a lot",
  noone: "no one", ofcourse: "of course", happend: "happened", happenned: "happened", stoped: "stopped",
  comming: "coming", writting: "writing", suddently: "suddenly", suprise: "surprise",
  suprised: "surprised", truely: "truly", similiar: "similar", remeber: "remember", rember: "remember",
  remebered: "remembered", intresting: "interesting", imediately: "immediately",
  immediatly: "immediately", familar: "familiar", foriegn: "foreign", fourty: "forty", greatful: "grateful",
  hieght: "height", lenght: "length", strenght: "strength", libary: "library", orignal: "original",
  posible: "possible", presense: "presence", sentance: "sentence", speach: "speech", tounge: "tongue",
  vaccum: "vacuum", visable: "visible", nieghbor: "neighbor", nieghbors: "neighbors",
  buisness: "business", calender: "calendar", concious: "conscious", curiousity: "curiosity",
  enterance: "entrance", excercise: "exercise", guage: "gauge", gaurd: "guard", jewlery: "jewelry",
  maintenence: "maintenance", mischevious: "mischievous", neccessary: "necessary",
  oppurtunity: "opportunity", resturant: "restaurant", shedule: "schedule", sincerly: "sincerely",
  tatoo: "tattoo", threshhold: "threshold", twelth: "twelfth", vegtable: "vegetable",
  // the words ghost stories need
  dissapear: "disappear", dissapeared: "disappeared", dissapears: "disappears", mysterous: "mysterious",
  cemetary: "cemetery", graveyeard: "graveyard", pumkin: "pumpkin", pumkins: "pumpkins",
  skeliton: "skeleton", skeleten: "skeleton", marshmellow: "marshmallow", marshmellows: "marshmallows",
  flashlite: "flashlight", witchs: "witches", gost: "ghost", ghsot: "ghost", ghots: "ghost",
  halloween: "Halloween", thanksgiving: "Thanksgiving", christmas: "Christmas",
  monday: "Monday", tuesday: "Tuesday", wednesday: "Wednesday", wensday: "Wednesday", wendsday: "Wednesday",
  thursday: "Thursday", friday: "Friday", saturday: "Saturday", sunday: "Sunday",
  january: "January", febuary: "February", february: "February", april: "April", june: "June",
  july: "July", september: "September", october: "October", november: "November", december: "December",
};

const BOUNDARY = /^[\s.,!?;:)\]"”]$/; // typing one of these ends a word
const WORD_BEFORE = /([A-Za-z']+)$/;

// Keep the capital the writer typed ("Teh" becomes "The"); fixes that are capitalised anyway stay so.
const matchCase = (typed, fix) => (typed[0] === typed[0].toUpperCase() && typed[0] !== typed[0].toLowerCase()
  ? fix[0].toUpperCase() + fix.slice(1) : fix);

export function fixFor(word) {
  const fix = FIXES[word.toLowerCase()];
  return fix && fix !== word ? matchCase(word, fix) : null;
}

// Replace text the way typing does, so Ctrl+Z can undo it; falls back where execCommand is gone.
function replace(box, start, end, text) {
  box.setSelectionRange(start, end);
  if (!document.execCommand("insertText", false, text)) box.setRangeText(text, start, end, "end");
}

// Watch a textarea. `enabled()` is read on every word, so a switch can turn it off; `onFix(from, to)`
// is told about each fix (to show it), and `onFix(from, to, true)` when one is undone.
export function attachAutocorrect(box, { enabled = () => true, onFix = () => {} } = {}) {
  let last = null; // the latest fix, which Backspace can undo: { start, typed, fixed, after }
  const keep = new Set(); // words the writer put back on purpose: never fixed again in this box
  let busy = false;

  box.addEventListener("input", (event) => {
    if (busy || event.inputType !== "insertText" || !event.data || !BOUNDARY.test(event.data) || !enabled()) {
      if (event.inputType !== "insertText") last = null;
      return;
    }
    const caret = box.selectionStart;
    const before = box.value.slice(0, caret - event.data.length);
    const typed = before.match(WORD_BEFORE)?.[1];
    if (!typed || keep.has(typed.toLowerCase())) return;
    const fixed = fixFor(typed);
    if (!fixed) return;
    const start = before.length - typed.length;
    busy = true;
    replace(box, start, start + typed.length, fixed);
    const after = start + fixed.length + event.data.length;
    box.setSelectionRange(after, after);
    busy = false;
    last = { start, typed, fixed, after };
    onFix(typed, fixed);
  });

  box.addEventListener("keydown", (event) => {
    if (event.key !== "Backspace" || !last) return;
    const { start, typed, fixed, after } = last;
    last = null;
    if (box.selectionStart !== after || box.selectionEnd !== after || box.value.slice(start, start + fixed.length) !== fixed) return;
    event.preventDefault();
    busy = true;
    replace(box, start, after, typed); // the word as it was typed, without the space that triggered the fix
    busy = false;
    keep.add(typed.toLowerCase());
    onFix(typed, fixed, true);
  });

  box.addEventListener("pointerdown", () => { last = null; });
}

// A box for writing a story: the browser's spell check, sentence capitals on phones, and autocorrect.
export function storyBox(attrs = {}) {
  const box = document.createElement("textarea");
  Object.assign(box, { spellcheck: true, lang: "en", ...attrs });
  box.setAttribute("autocapitalize", "sentences");
  box.setAttribute("autocorrect", "on"); // Safari and phone keyboards
  return box;
}
