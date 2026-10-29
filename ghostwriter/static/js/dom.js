// Small DOM helpers. Text always goes in via textContent, so stories can never inject HTML.

// Empty children (null, false, "") are skipped, which keeps `condition && el(...)` readable.
export const present = (children) =>
  children.filter((c) => c !== null && c !== undefined && c !== false && c !== "");

export function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  Object.assign(node, props);
  node.append(...present(children));
  return node;
}

export const $ = (selector) => document.querySelector(selector);

// SQLite stores UTC ("2026-10-28 10:47:38"); show it in the viewer's time zone as "28 Oct 2026, 4:59 pm".
export const localTime = (utc) => new Date(utc.replace(" ", "T") + "Z").toLocaleString("en-IN", {
  day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit",
});
