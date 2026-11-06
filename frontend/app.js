// Vaani frontend. Plain ES module, no build step.
//
// Flow of one turn:
//   mic tap -> record (16 kHz mono WAV, made in the browser) -> POST /audio -> server runs Prisma
//   + the dialogue manager -> JSON back -> redraw the form -> fetch Timbre audio for each bot
//   message -> play it -> (hands-free) listen again.
//
// Prisma accepts WAV but not WebM, which is what MediaRecorder produces in Chrome. So we capture
// raw samples with the Web Audio API and write the WAV ourselves. Same format on every browser.

const $ = (id) => document.getElementById(id);

// ----------------------------------------------------------------------------- text
const UI = {
  hi: {
    tap: "बोलने के लिए दबाइए",
    listening: "सुन रही हूँ… पूरा होने पर दबाइए",
    thinking: "समझ रही हूँ…",
    speaking: "बोल रही हूँ… रोकने के लिए दबाइए",
    complete: "फ़ॉर्म पूरा हो गया",
    heard: "आपने कहा",
    typeLabel: "अपना जवाब लिखिए",
    placeholder: "या यहाँ जवाब लिखिए",
    send: "भेजें",
    handsFree: "अपने आप सुनें",
    restart: "फिर से शुरू करें",
    pdf: "PDF डाउनलोड करें",
    del: "मेरा डेटा मिटाएँ",
    count: (a, b) => `${a} / ${b} भरे`,
    privacy: "आपके जवाब सिर्फ़ मेमोरी में रहते हैं। 30 मिनट बाद या पेज छोड़ने पर मिट जाते हैं।",
    sayYesNo: "हाँ या नहीं बोलिए",
    micDenied: "माइक्रोफ़ोन की अनुमति नहीं मिली। आप नीचे लिखकर जवाब दे सकते हैं।",
    noSpeech: "कुछ सुनाई नहीं दिया। माइक दबाकर फिर बोलिए।",
    network: "सर्वर से जुड़ नहीं पाए। कृपया दोबारा कोशिश कीजिए।",
    stamp: "✓ सही",
    mic: "बोलिए",
  },
  en: {
    tap: "Tap to talk",
    listening: "Listening… tap when you're done",
    thinking: "Thinking…",
    speaking: "Speaking… tap to interrupt",
    complete: "Form complete",
    heard: "You said",
    typeLabel: "Type your answer",
    placeholder: "Or type your answer here",
    send: "Send",
    handsFree: "Hands-free",
    restart: "Start over",
    pdf: "Download PDF",
    del: "Delete my data",
    count: (a, b) => `${a} of ${b}`,
    privacy: "Answers stay in memory only and are deleted after 30 minutes or when you leave.",
    sayYesNo: "Say yes or no",
    micDenied: "Microphone access was blocked. You can type your answers below.",
    noSpeech: "I didn't hear anything. Tap the mic and try again.",
    network: "Couldn't reach the server. Please try again.",
    stamp: "✓ OK",
    mic: "Talk",
  },
};

// ----------------------------------------------------------------------------- state
const S = {
  sid: null,
  lang: "hi",
  mode: "idle",          // idle | listening | thinking | speaking
  rec: null,
  audio: new Audio(),
  stopPlayback: null,
  playToken: 0,
  prevStatus: {},
  done: false,
};

const tr = (k, ...a) => {
  const v = UI[S.lang][k];
  return typeof v === "function" ? v(...a) : v;
};

// ----------------------------------------------------------------------------- tiny helpers
async function api(path, opts) {
  let r;
  try {
    r = await fetch(path, opts);
  } catch {
    const e = new Error(tr("network"));
    e.code = "network";
    throw e;
  }
  if (!r.ok) {
    let j = {};
    try { j = await r.json(); } catch { /* not JSON */ }
    const e = new Error(j.message || `Request failed (${r.status})`);
    e.code = j.error || "http_" + r.status;
    e.status = r.status;
    throw e;
  }
  return r;
}

let toastTimer = null;
function toast(msg) {
  const el = $("toast");
  el.textContent = msg;
  el.hidden = !msg;
  clearTimeout(toastTimer);
  if (msg) toastTimer = setTimeout(() => { el.hidden = true; }, 9000);
}

function setMode(mode) {
  S.mode = mode;
  const mic = $("mic");
  mic.dataset.mode = mode;
  mic.setAttribute("aria-pressed", String(mode === "listening"));
  mic.setAttribute("aria-label", tr("mic"));
  $("status").textContent =
    S.done && mode === "idle" ? tr("complete")
    : { idle: tr("tap"), listening: tr("listening"), thinking: tr("thinking"), speaking: tr("speaking") }[mode];
  mic.disabled = S.done && mode === "idle";
}

function applyStaticText() {
  document.documentElement.lang = S.lang === "hi" ? "hi" : "en";
  $("heardLabel").textContent = tr("heard");
  $("typeLabel").textContent = tr("typeLabel");
  $("typeInput").placeholder = tr("placeholder");
  $("typeSend").textContent = tr("send");
  $("handsFreeLabel").textContent = tr("handsFree");
  $("restartBtn").textContent = tr("restart");
  $("pdfLink").textContent = tr("pdf");
  $("deleteBtn").textContent = tr("del");
  $("privacyNote").textContent = tr("privacy");
  setMode(S.mode);
}

// ----------------------------------------------------------------------------- audio playback
function unlockAudio() {
  // Mobile browsers only allow audio that starts from a tap. Play 50 ms of silence inside the tap.
  try {
    const samples = new Int16Array(800);
    const blob = encodeWav([samples], 16000);
    const url = URL.createObjectURL(blob);
    S.audio.src = url;
    S.audio.play().catch(() => {});
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch { /* harmless */ }
}

function stopAudio() {
  S.playToken++;
  try { S.audio.pause(); } catch { /* ignore */ }
  if ("speechSynthesis" in window) window.speechSynthesis.cancel();
  if (S.stopPlayback) { const f = S.stopPlayback; S.stopPlayback = null; f(); }
}

function playUrl(url) {
  return new Promise((resolve) => {
    const finish = () => {
      S.audio.onended = S.audio.onerror = null;
      if (S.stopPlayback === finish) S.stopPlayback = null;
      resolve();
    };
    S.stopPlayback = finish;
    S.audio.onended = finish;
    S.audio.onerror = finish;
    S.audio.src = url;
    S.audio.play().catch(finish);
  });
}

// Used only if the Timbre call fails, so the demo never goes silent.
function browserSpeak(m) {
  return new Promise((resolve) => {
    if (!("speechSynthesis" in window)) return resolve();
    const u = new SpeechSynthesisUtterance(m.text);
    u.lang = m.tts_lang === "en-IN" ? "en-IN" : "hi-IN";
    const finish = () => { if (S.stopPlayback === finish) S.stopPlayback = null; resolve(); };
    S.stopPlayback = finish;
    u.onend = u.onerror = finish;
    window.speechSynthesis.speak(u);
  });
}

async function speak(messages, token) {
  for (const m of messages) {
    if (token !== S.playToken) return;
    try {
      const r = await api(`/api/sessions/${S.sid}/messages/${m.id}/audio`);
      const blob = await r.blob();
      if (token !== S.playToken) return;
      const url = URL.createObjectURL(blob);
      await playUrl(url);
      URL.revokeObjectURL(url);
    } catch (e) {
      if (token !== S.playToken) return;
      console.warn("Timbre audio failed, using the browser voice:", e.message);
      await browserSpeak(m);
    }
  }
}

// ----------------------------------------------------------------------------- recording
function encodeWav(chunksInt16, sampleRate) {
  const len = chunksInt16.reduce((n, c) => n + c.length, 0);
  const buf = new ArrayBuffer(44 + len * 2);
  const v = new DataView(buf);
  const w = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
  w(0, "RIFF"); v.setUint32(4, 36 + len * 2, true); w(8, "WAVE"); w(12, "fmt ");
  v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
  v.setUint32(24, sampleRate, true); v.setUint32(28, sampleRate * 2, true);
  v.setUint16(32, 2, true); v.setUint16(34, 16, true); w(36, "data"); v.setUint32(40, len * 2, true);
  let o = 44;
  for (const c of chunksInt16) for (let i = 0; i < c.length; i++, o += 2) v.setInt16(o, c[i], true);
  return new Blob([buf], { type: "audio/wav" });
}

function downsampleTo16k(float32, inRate) {
  const OUT = 16000;
  const ratio = inRate / OUT;
  const n = Math.floor(float32.length / ratio);
  const out = new Int16Array(n);
  for (let i = 0; i < n; i++) {
    const a = Math.floor(i * ratio), b = Math.min(Math.floor((i + 1) * ratio), float32.length);
    let sum = 0;
    for (let j = a; j < b; j++) sum += float32[j];
    const s = Math.max(-1, Math.min(1, sum / Math.max(1, b - a)));
    out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return out;
}

const WORKLET_SRC = `
class PcmTap extends AudioWorkletProcessor {
  constructor() { super(); this.buf = []; this.n = 0; }
  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (ch) {
      this.buf.push(ch.slice(0)); this.n += ch.length;
      if (this.n >= 2048) {
        const out = new Float32Array(this.n); let o = 0;
        for (const b of this.buf) { out.set(b, o); o += b.length; }
        this.port.postMessage(out, [out.buffer]); this.buf = []; this.n = 0;
      }
    }
    return true;
  }
}
registerProcessor("pcm-tap", PcmTap);`;

const MAX_SECONDS = 28;       // Prisma REST accepts up to 30 s
const SILENCE_MS = 1400;      // stop this long after the person stops talking
const NO_SPEECH_MS = 9000;    // give up if nobody speaks at all

async function createRecorder(onLevel, onAutoStop) {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
  });
  const AC = window.AudioContext || window.webkitAudioContext;
  const ctx = new AC();
  if (ctx.state === "suspended") await ctx.resume();
  const source = ctx.createMediaStreamSource(stream);

  const chunks = [];
  const t0 = performance.now();
  let noise = 0.004, calibrated = false, spoke = false, lastVoice = 0, stopped = false;

  const handle = (f32) => {
    if (stopped) return;
    chunks.push(f32);
    let sum = 0;
    for (let i = 0; i < f32.length; i++) sum += f32[i] * f32[i];
    const rms = Math.sqrt(sum / f32.length);
    const now = performance.now();
    onLevel(Math.min(1, rms * 9));
    if (!calibrated && now - t0 < 350) { noise = Math.max(noise, Math.min(rms, 0.03)); return; }
    calibrated = true;
    if (rms > Math.max(0.018, noise * 3)) { spoke = true; lastVoice = now; }
    if (spoke && now - lastVoice > SILENCE_MS) onAutoStop();
    else if (!spoke && now - t0 > NO_SPEECH_MS) onAutoStop();
    else if (now - t0 > MAX_SECONDS * 1000) onAutoStop();
  };

  let node = null;
  if (ctx.audioWorklet) {
    try {
      const url = URL.createObjectURL(new Blob([WORKLET_SRC], { type: "text/javascript" }));
      await ctx.audioWorklet.addModule(url);
      URL.revokeObjectURL(url);
      node = new AudioWorkletNode(ctx, "pcm-tap");
      node.port.onmessage = (e) => handle(e.data);
    } catch { node = null; }
  }
  if (!node) {                                   // older browsers
    node = ctx.createScriptProcessor(4096, 1, 1);
    node.onaudioprocess = (e) => handle(new Float32Array(e.inputBuffer.getChannelData(0)));
  }
  source.connect(node);
  node.connect(ctx.destination);                 // outputs silence; some browsers need the connection

  return {
    async stop() {
      stopped = true;
      try { source.disconnect(); node.disconnect(); } catch { /* ignore */ }
      stream.getTracks().forEach((t) => t.stop());
      const rate = ctx.sampleRate;
      try { await ctx.close(); } catch { /* ignore */ }
      const total = chunks.reduce((n, c) => n + c.length, 0);
      const all = new Float32Array(total);
      let o = 0;
      for (const c of chunks) { all.set(c, o); o += c.length; }
      const pcm = downsampleTo16k(all, rate);
      return { blob: encodeWav([pcm], 16000), seconds: pcm.length / 16000, spoke };
    },
    cancel() {
      stopped = true;
      try { source.disconnect(); node.disconnect(); } catch { /* ignore */ }
      stream.getTracks().forEach((t) => t.stop());
      ctx.close().catch(() => {});
    },
  };
}

async function startListening() {
  if (S.mode === "listening" || S.mode === "thinking" || S.done || !S.sid) return;
  stopAudio();
  toast("");
  try {
    S.rec = await createRecorder(
      (lvl) => $("mic").style.setProperty("--lvl", lvl.toFixed(2)),
      () => finishListening(false),
    );
  } catch (e) {
    S.rec = null;
    setMode("idle");
    toast(tr("micDenied"));
    $("typeInput").focus();
    return;
  }
  setMode("listening");
}

async function finishListening(manual) {
  const rec = S.rec;
  if (!rec || S.mode !== "listening") return;
  S.rec = null;
  setMode("thinking");
  $("mic").style.setProperty("--lvl", "0");
  const { blob, seconds, spoke } = await rec.stop();
  // Don't spend credits on silence. A manual tap-to-stop is trusted if there is a little audio.
  if (!(spoke || (manual && seconds >= 0.6)) || seconds < 0.3) {
    setMode("idle");
    toast(tr("noSpeech"));
    return;
  }
  const fd = new FormData();
  fd.append("audio", blob, "answer.wav");
  try {
    const r = await api(`/api/sessions/${S.sid}/audio`, { method: "POST", body: fd });
    await handleResponse(await r.json());
  } catch (e) {
    onTurnError(e);
  }
}

function onTurnError(e) {
  setMode("idle");
  toast(e.message);
  if (e.code === "no_session") { setTimeout(() => backToLanding(), 1800); return; }
  if (String(e.code).startsWith("stt_") || e.code === "quota" || e.code === "network") $("typeInput").focus();
}

// ----------------------------------------------------------------------------- rendering
function renderForm(form) {
  $("sheetTitle").textContent = form.title;
  $("sheetCount").textContent = tr("count", form.done, form.total);
  $("meterBar").style.width = `${Math.round((form.done / form.total) * 100)}%`;
  const rows = $("rows");
  rows.replaceChildren();
  const nextPrev = {};
  form.fields.forEach((f, i) => {
    nextPrev[f.id] = f.status;
    const li = document.createElement("li");
    li.className = "row";
    li.dataset.status = f.status;
    if (f.status === "done" && S.prevStatus[f.id] && S.prevStatus[f.id] !== "done") li.classList.add("just-done");

    const n = document.createElement("span");
    n.className = "row-n";
    n.textContent = String(i + 1);
    const body = document.createElement("div");
    body.className = "row-body";
    const label = document.createElement("span");
    label.className = "row-label";
    label.textContent = f.label;
    const value = document.createElement("span");
    value.className = "row-value";
    value.textContent = f.status === "confirm" ? f.pending : f.display;
    body.append(label, value);
    if (f.status === "confirm") {
      const hint = document.createElement("span");
      hint.className = "row-hint";
      hint.textContent = tr("sayYesNo");
      body.append(hint);
    }
    const stamp = document.createElement("span");
    stamp.className = "stamp";
    stamp.textContent = tr("stamp");
    li.append(n, body, stamp);
    rows.append(li);
    if (f.status === "active" || f.status === "confirm") li.scrollIntoView({ block: "nearest", behavior: "smooth" });
  });
  S.prevStatus = nextPrev;
  const complete = !!form.complete;
  $("sheetFoot").hidden = !complete;
  if (complete) $("pdfLink").href = `/api/sessions/${S.sid}/pdf`;
}

async function handleResponse(data) {
  S.sid = data.session_id;
  S.done = !!data.done;
  renderForm(data.form);

  const bot = $("botText");
  bot.textContent = data.messages.map((m) => m.text).join(" ");
  bot.classList.remove("fresh");
  void bot.offsetWidth;
  bot.classList.add("fresh");

  const heard = $("heard");
  if (data.heard) { $("heardText").textContent = data.heard; heard.hidden = false; }
  else heard.hidden = true;

  stopAudio();
  const token = S.playToken;
  setMode("speaking");
  await speak(data.messages, token);
  if (token !== S.playToken) return;       // interrupted by the person: they are already in control

  setMode("idle");
  if (!S.done && $("handsFree").checked) await startListening();
}

// ----------------------------------------------------------------------------- session control
async function startSession(lang) {
  S.lang = lang;
  S.done = false;
  S.prevStatus = {};
  unlockAudio();
  $("landingError").hidden = true;
  applyStaticText();
  try {
    const r = await api("/api/sessions", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ lang }),
    });
    const data = await r.json();
    $("landing").hidden = true;
    $("session").hidden = false;
    $("topActions").hidden = false;
    $("heard").hidden = true;
    $("typeInput").value = "";
    toast("");
    await handleResponse(data);
  } catch (e) {
    $("landingError").textContent = e.message;
    $("landingError").hidden = false;
  }
}

function endSession() {
  stopAudio();
  if (S.rec) { S.rec.cancel(); S.rec = null; }
  const sid = S.sid;
  S.sid = null;
  if (sid) fetch(`/api/sessions/${sid}`, { method: "DELETE", keepalive: true }).catch(() => {});
}

function backToLanding() {
  endSession();
  S.done = false;
  setMode("idle");
  $("session").hidden = true;
  $("topActions").hidden = true;
  $("landing").hidden = false;
  $("rows").replaceChildren();
  $("sheetFoot").hidden = true;
  toast("");
}

// ----------------------------------------------------------------------------- events
$("startHi").addEventListener("click", () => startSession("hi"));
$("startEn").addEventListener("click", () => startSession("en"));

$("mic").addEventListener("click", () => {
  unlockAudio();
  if (S.mode === "listening") finishListening(true);
  else startListening();
});

$("typeForm").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const text = $("typeInput").value.trim();
  if (!text || !S.sid || S.mode === "thinking") return;
  if (S.rec) { S.rec.cancel(); S.rec = null; }
  stopAudio();
  $("typeInput").value = "";
  setMode("thinking");
  try {
    const r = await api(`/api/sessions/${S.sid}/text`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }),
    });
    await handleResponse(await r.json());
  } catch (e) {
    onTurnError(e);
  }
});

$("restartBtn").addEventListener("click", async () => {
  const lang = S.lang;
  endSession();
  await startSession(lang);
});
$("deleteBtn").addEventListener("click", backToLanding);

// Space bar toggles the mic when the focus is not in a text box.
document.addEventListener("keydown", (e) => {
  if (e.code !== "Space" || e.repeat || $("session").hidden) return;
  const tag = (e.target.tagName || "").toLowerCase();
  if (tag === "input" || tag === "textarea" || tag === "button" || tag === "a") return;
  e.preventDefault();
  $("mic").click();
});

// Delete the server-side session when the tab closes.
window.addEventListener("pagehide", () => {
  if (S.sid) navigator.sendBeacon(`/api/sessions/${S.sid}`);
});

// Tell the visitor early if the server has no API key (typing still works).
fetch("/api/health").then((r) => r.json()).then((h) => {
  if (!h.gnani_configured) {
    $("landingNote").textContent =
      "Demo note: this server has no Gnani API key yet, so voice is off. You can still type your answers.";
  }
}).catch(() => {});

applyStaticText();
