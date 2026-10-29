// "Ghost handwriting": Gemma's words appear one piece at a time, each fading in like wet ink.
// Citations arrive separately (the server takes [S3] out of the text) and become small numbered
// links straight away, so a raw marker is never on screen.

import { el } from "./dom.js";

export function quill(node, linkFor = () => null) {
  node.replaceChildren();
  node.classList.add("ghost-text", "writing");
  let text = "";
  const cited = []; // story ids in the order of their numbers: [1], [2], ...
  let last = null;
  return {
    write(piece) {
      text += piece;
      last = null;
      node.append(el("span", { className: "ink", textContent: piece }));
    },
    // A citation of story `id`: numbered by first appearance; repeats in a row show one mark.
    cite(id) {
      const link = linkFor(id); // {href, label}, or null for a story Gemma was never shown: dropped
      if (!link || id === last) return;
      last = id;
      if (!cited.includes(id)) cited.push(id);
      const n = cited.indexOf(id) + 1;
      node.append(el("sup", { className: "cite" },
        el("a", { href: link.href, title: link.label, ariaLabel: `Source ${n}: ${link.label}`, textContent: `[${n}]` })));
    },
    finish() {
      node.classList.remove("writing");
      return text;
    },
    get text() { return text; },
    get cited() { return cited; },
  };
}
