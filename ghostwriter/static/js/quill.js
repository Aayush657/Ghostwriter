// "Ghost handwriting": Gemma's words appear one piece at a time, each fading in like wet ink.

import { el } from "./dom.js";

export function quill(node) {
  node.replaceChildren();
  node.classList.add("handwriting", "writing");
  let text = "";
  return {
    write(piece) {
      text += piece;
      node.append(el("span", { className: "ink", textContent: piece }));
    },
    // When writing ends, re-render the text once, turning [S12]-style citations into story links.
    finish(linkFor = () => null) {
      node.classList.remove("writing");
      node.replaceChildren(...withCitations(text, linkFor));
      return text;
    },
    get text() { return text; },
  };
}

function withCitations(text, linkFor) {
  const named = new Set(); // show a story's title on its first citation, then just a small mark
  return text.split(/(\[S\d+\])/).filter(Boolean).map((part) => {
    const id = part.match(/^\[S(\d+)\]$/)?.[1];
    if (!id) return part;
    const link = linkFor(Number(id));  // {href, label} or null
    // A citation of a story Gemma was never shown is dropped rather than shown as a dead link.
    if (!link) return "";
    const first = !named.has(id);
    named.add(id);
    return el("a", { href: link.href, className: first ? "cite" : "cite short", title: link.label,
                     textContent: first ? link.label : "" });
  });
}
