// Talking to the local Ghostwriter server. Nothing here ever leaves this machine.

const FIELDS = { title: "The title", transcript: "The words", question: "The question", new: "The tag",
                 mood: "The mood", text: "The story", file: "The file" };

// FastAPI's error detail is a sentence, or (for invalid input) a list of problems. Always plain words.
export function readableError(detail, status) {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((problem) => {
      const field = FIELDS[problem.loc?.at(-1)] || "That value";
      if (problem.type === "string_too_short" && problem.ctx?.min_length > 1) return `${field} is too short (at least ${problem.ctx.min_length} characters).`;
      if (problem.type === "string_too_short" || problem.type === "missing") return `${field} can't be empty.`;
      if (problem.type === "string_too_long") return `${field} is too long (at most ${problem.ctx?.max_length} characters).`;
      if (problem.type === "literal_error" || problem.type === "enum") return `${field} isn't one of the choices.`;
      return `${field}: ${problem.msg}.`;
    }).join(" ");
  }
  return `Something went wrong (${status}).`;
}

async function failure(res) {
  const body = await res.json().catch(() => ({}));
  return Object.assign(new Error(readableError(body.detail, res.status)), { status: res.status });
}

export async function api(path, options) {
  const res = await fetch(path, options);
  if (!res.ok) throw await failure(res);
  return res.status === 204 ? {} : res.json().catch(() => ({}));
}

// Send JSON with any method (PATCH, DELETE, ...).
export const send = (path, method, body) => api(path, {
  method,
  headers: body ? { "Content-Type": "application/json" } : {},
  body: body ? JSON.stringify(body) : undefined,
});

// POST and read a Server-Sent Events reply as it arrives.
// `handlers` maps event names ("token", "cite", "done", ...) to functions that get the parsed data.
// Aborting `signal` stops the request; the server then stops Gemma too.
export async function streamEvents(path, body, handlers, signal) {
  const res = await fetch(path, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
    signal,
  });
  if (!res.ok) throw await failure(res);
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    signal?.throwIfAborted(); // text already on its way is dropped once the visitor cancels
    if (done) return;
    buffer += value;
    let end;
    while ((end = buffer.indexOf("\n\n")) >= 0) {
      const [eventLine, dataLine] = buffer.slice(0, end).split("\n");
      buffer = buffer.slice(end + 2);
      handlers[eventLine.slice("event: ".length)]?.(JSON.parse(dataLine.slice("data: ".length)));
    }
  }
}
