// Talking to the local Ghostwriter server. Nothing here ever leaves this machine.

export async function api(path, options) {
  const res = await fetch(path, options);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `${res.status} ${res.statusText}`);
  return body;
}

// Send JSON with any method (PATCH, DELETE, ...).
export const send = (path, method, body) => api(path, {
  method,
  headers: body ? { "Content-Type": "application/json" } : {},
  body: body ? JSON.stringify(body) : undefined,
});

// POST and read a Server-Sent Events reply as it arrives.
// `handlers` maps event names ("token", "done", ...) to functions that get the parsed data.
// Aborting `signal` stops the request; the server then stops Gemma too.
export async function streamEvents(path, body, handlers, signal) {
  const res = await fetch(path, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
    signal,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `${res.status} ${res.statusText}`);
  }
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
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
