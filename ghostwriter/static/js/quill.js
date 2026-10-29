// "Ghost handwriting": Gemma's words appear one piece at a time, each fading in like wet ink.

import { el } from "./dom.js";

export function quill(node) {
  node.replaceChildren();
  node.classList.add("ghost-text", "writing");
  let text = "";
  let cited = [];
  return {
    write(piece) {
      text += piece;
      node.append(el("span", { className: "ink", textContent: piece }));
    },
    // When writing ends, re-render the text once, turning [S12]-style citations into small numbered links.
    finish(linkFor = () => null) {
      node.classList.remove("writing");
      const { parts, order } = withCitations(text, linkFor);
      cited = order;
      node.replaceChildren(...parts);
      return text;
    },
    get text() { return text; },
    get cited() { return cited; }, // story ids in the order of their numbers: [1], [2], ...
  };
}

// "...in Lucknow [S3]. A brass pot [S3]." -> "...in Lucknow[1]. A brass pot."
// Sources are numbered by first citation, and repeats of the same source in a row show one mark.
function withCitations(text, linkFor) {
  const order = [];
  let last = null;
  const parts = text.split(/\s*(\[S\d+\])/).filter(Boolean).map((part) => {
    const id = Number(part.match(/^\[S(\d+)\]$/)?.[1]);
    if (!id) return part;
    const link = linkFor(id); // {href, label}, or null for a story Gemma was never shown: dropped
    if (!link || id === last) return "";
    last = id;
    if (!order.includes(id)) order.push(id);
    const n = order.indexOf(id) + 1;
    return el("sup", { className: "cite" },
      el("a", { href: link.href, title: link.label, ariaLabel: `Source ${n}: ${link.label}`, textContent: `[${n}]` }));
  });
  return { parts, order };
}
