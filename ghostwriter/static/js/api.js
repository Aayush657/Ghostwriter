// Talking to the local Ghostwriter server. Nothing here ever leaves this machine.

export async function api(path, options) {
  const res = await fetch(path, options);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `${res.status} ${res.statusText}`);
  return body;
}

// POST and read a Server-Sent Events reply as it arrives.
// `handlers` maps event names ("token", "done", ...) to functions that get the parsed data.
export async function streamEvents(path, body, handlers) {
  const res = await fetch(path, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
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
