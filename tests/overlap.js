// Finds decorations (moon, cobweb, crystal ball, graveyard, speech bubble, the whisper) that cover
// text or show through behind it. Runs in the page (Playwright: page.evaluate). Returns a list of
// problems, each "decoration over|behind 'text'".
() => {
  const DECORATION = ".moon, .web, .spider, .orb, .skyline, .bubble, .mascot, .whisper";
  const isDecoration = (node) => node instanceof Element && node.closest(DECORATION);
  const opaque = (node) => {
    const style = getComputedStyle(node);
    const alpha = style.backgroundColor.match(/rgba?\(([^)]+)\)/)?.[1].split(",")[3];
    return (alpha === undefined ? style.backgroundColor !== "transparent" : Number(alpha) === 1)
      && style.backgroundColor !== "rgba(0, 0, 0, 0)";
  };
  const problems = new Set();
  // Decorations ignore the mouse (pointer-events: none), which also hides them from elementsFromPoint.
  const probe = document.head.appendChild(document.createElement("style"));
  probe.textContent = ".scene, .scene *, .web, .web *, .orb, .orb *, .bubble, .mascot, .whisper { pointer-events: auto !important; }";
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let text = walker.nextNode(); text; text = walker.nextNode()) {
    const owner = text.parentElement;
    if (!text.textContent.trim() || !owner || isDecoration(owner) || owner.closest("#toast, dialog, .scene")) continue;
    const range = document.createRange();
    range.selectNodeContents(text);
    for (const rect of range.getClientRects()) {
      if (rect.bottom < 0 || rect.top > innerHeight || rect.width < 2) continue;
      for (const fx of [0.05, 0.3, 0.5, 0.7, 0.95]) {
        const x = rect.left + rect.width * fx;
        const y = rect.top + rect.height / 2;
        if (x < 0 || x >= innerWidth) continue;
        const stack = document.elementsFromPoint(x, y);
        const at = stack.findIndex((node) => node === owner || owner.contains(node));
        if (at < 0) continue;
        const above = stack.slice(0, at).find(isDecoration);
        if (above) { problems.add(`${above.className.baseVal ?? above.className} over '${text.textContent.trim().slice(0, 40)}'`); continue; }
        for (const node of stack.slice(at)) { // look down through the layers until something opaque
          if (isDecoration(node)) { problems.add(`${node.className.baseVal ?? node.className} behind '${text.textContent.trim().slice(0, 40)}'`); break; }
          if (opaque(node)) break;
        }
      }
    }
  }
  probe.remove();
  return [...problems];
}
