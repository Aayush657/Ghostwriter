// Recording in the browser with MediaRecorder. The audio only ever goes to the local server.

const EXTENSIONS = { ogg: "ogg", mp4: "m4a", webm: "webm" };

// Start recording; returns { stop() } where stop() resolves to a File ready to upload.
export async function startRecording() {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const recorder = new MediaRecorder(stream);
  const chunks = [];
  recorder.ondataavailable = (event) => { if (event.data.size) chunks.push(event.data); };
  recorder.start(1000); // a chunk every second, so a crash loses at most a second
  return {
    stop: () => new Promise((resolve) => {
      recorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop()); // releases the mic (light goes off)
        const type = recorder.mimeType || "audio/webm";
        const ext = Object.entries(EXTENSIONS).find(([key]) => type.includes(key))?.[1] || "webm";
        resolve(new File(chunks, `recording.${ext}`, { type }));
      };
      recorder.stop();
    }),
  };
}

// Why the mic didn't start, in the ghost's words, plus the plain fix.
export function micProblem(error) {
  if (error.name === "NotAllowedError") {
    return { ghost: "The ghost cannot hear you: the microphone is sealed.",
             fix: "Click the icon at the left of the address bar and allow the microphone, then try again." };
  }
  if (error.name === "NotFoundError") {
    return { ghost: "There is no ear in this room for the ghost to borrow.",
             fix: "No microphone was found. Plug one in, or upload a recording instead." };
  }
  return { ghost: "The ghost strains to listen, but hears nothing.", fix: error.message };
}
