// Recording in the browser with MediaRecorder. The audio only ever goes to the local server.

const EXTENSIONS = { ogg: "ogg", mp4: "m4a", webm: "webm" };

// Ask for the microphone and start recording. Resolves once recording has begun, with
// { stop() -> Promise<File>, cancel(), level() -> 0..1 }. Rejects with the browser's error if the
// microphone can't be used (see micProblem).
export async function startRecording() {
  if (!navigator.mediaDevices?.getUserMedia) {
    throw Object.assign(new Error("No microphone access on this page."), { name: "InsecureContext" });
  }
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const recorder = new MediaRecorder(stream);
  const chunks = [];
  recorder.ondataavailable = (event) => { if (event.data.size) chunks.push(event.data); };
  recorder.start(1000); // a chunk every second, so a crash loses at most a second

  // The level meter: how loud the microphone is right now.
  const context = new AudioContext();
  const analyser = context.createAnalyser();
  analyser.fftSize = 512;
  context.createMediaStreamSource(stream).connect(analyser);
  const samples = new Uint8Array(analyser.fftSize);
  const release = () => {
    stream.getTracks().forEach((track) => track.stop()); // releases the mic (the browser's light goes off)
    context.close().catch(() => {});
  };

  return {
    level() {
      analyser.getByteTimeDomainData(samples);
      let peak = 0;
      for (const s of samples) peak = Math.max(peak, Math.abs(s - 128));
      return Math.min(1, peak / 100);
    },
    stop: () => new Promise((resolve) => {
      recorder.onstop = () => {
        release();
        const type = recorder.mimeType || "audio/webm";
        const ext = Object.entries(EXTENSIONS).find(([key]) => type.includes(key))?.[1] || "webm";
        resolve(new File(chunks, `recording.${ext}`, { type }));
      };
      recorder.stop();
    }),
    cancel() {
      recorder.onstop = release;
      recorder.stop();
    },
  };
}

// Why the mic didn't start, in the ghost's words, plus the plain fix.
export function micProblem(error) {
  if (error.name === "NotAllowedError" || error.name === "SecurityError") {
    return { ghost: "The Archivist cannot hear you: the microphone is sealed.",
             fix: "The microphone was blocked or the request was dismissed. Click the icon at the left of the "
                + "address bar, allow the microphone for this page, then try again." };
  }
  if (error.name === "NotFoundError" || error.name === "OverconstrainedError") {
    return { ghost: "There is no ear in this room for the Archivist to borrow.",
             fix: "No microphone was found. Plug one in and try again, or upload a recording instead." };
  }
  if (error.name === "NotReadableError" || error.name === "AbortError") {
    return { ghost: "Another spirit is using the microphone.",
             fix: "The microphone is busy in another program (a call or another tab). Close it there and try again." };
  }
  if (error.name === "InsecureContext") {
    return { ghost: "This page cannot reach the microphone.",
             fix: "Open Ghostwriter at http://127.0.0.1:8000 (or localhost) so the browser allows the microphone." };
  }
  return { ghost: "The Archivist strains to listen, but hears nothing.",
           fix: `The microphone could not start (${error.message || error.name}). Try again, or upload a recording.` };
}
