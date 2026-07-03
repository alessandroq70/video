"use strict";

// ---------------------------------------------------------------------------
// "Unisci Video" — versione 100% browser, basata su ffmpeg.wasm.
// Nessun server: i video vengono elaborati localmente nel browser.
// ---------------------------------------------------------------------------

const { FFmpeg } = FFmpegWASM;
const { fetchFile, toBlobURL } = FFmpegUtil;

// Single-thread core: non richiede header COOP/COEP, quindi funziona su
// GitHub Pages senza configurazioni particolari.
const FFMPEG_BASE = "https://unpkg.com/@ffmpeg/ffmpeg@0.12.10/dist/umd";
// Il worker di ffmpeg è un "module worker" e carica il core via import(): serve
// quindi la build ESM del core (quella UMD non espone `export default`).
const CORE_BASE = "https://unpkg.com/@ffmpeg/core@0.12.6/dist/esm";
// Worker chunk di @ffmpeg/ffmpeg@0.12.10. Deve essere un URL assoluto.
const WORKER_URL = `${FFMPEG_BASE}/814.ffmpeg.js`;

const VIDEO_EXT = /\.(mp4|mov|m4v|avi|mkv|webm|wmv|flv|mpe?g|3gp)$/i;

let files = [];        // videos in merge order
let ffmpeg = null;     // lazily created FFmpeg instance
let logBuffer = [];     // captured ffmpeg log lines for the current command

const fileInput = document.getElementById("file-input");
const dropzone = document.getElementById("dropzone");
const fileListEl = document.getElementById("file-list");
const mergeBtn = document.getElementById("merge-btn");
const clearBtn = document.getElementById("clear-btn");
const statusEl = document.getElementById("status");
const progressWrap = document.getElementById("progress-wrap");
const progressBar = document.getElementById("progress-bar");

// --- Helpers ---------------------------------------------------------------

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function setStatus(message, kind) {
  statusEl.textContent = message || "";
  statusEl.className = "status" + (kind ? " " + kind : "");
}

function setProgress(fraction) {
  if (fraction == null) {
    progressWrap.hidden = true;
    progressBar.style.width = "0%";
    return;
  }
  progressWrap.hidden = false;
  const pct = Math.max(0, Math.min(100, Math.round(fraction * 100)));
  progressBar.style.width = pct + "%";
}

function isVideo(file) {
  return (file.type && file.type.startsWith("video/")) || VIDEO_EXT.test(file.name);
}

function extOf(name) {
  const m = /\.([a-z0-9]+)$/i.exec(name);
  return m ? m[1].toLowerCase() : "mp4";
}

function even(n) {
  return n % 2 === 0 ? n : n + 1;
}

// --- File list management --------------------------------------------------

function addFiles(fileListLike) {
  const incoming = Array.from(fileListLike);
  let skipped = 0;
  for (const file of incoming) {
    if (!isVideo(file)) { skipped++; continue; }
    const duplicate = files.some((f) => f.name === file.name && f.size === file.size);
    if (!duplicate) files.push(file);
  }
  render();
  setStatus(skipped > 0 ? `${skipped} file ignorato/i perché non è un video.` : "", skipped > 0 ? "error" : "");
}

function removeAt(index) { files.splice(index, 1); render(); }

function move(index, delta) {
  const target = index + delta;
  if (target < 0 || target >= files.length) return;
  [files[index], files[target]] = [files[target], files[index]];
  render();
}

function render() {
  fileListEl.innerHTML = "";
  files.forEach((file, i) => {
    const li = document.createElement("li");
    li.className = "file-item";
    li.innerHTML = `
      <span class="file-index">${i + 1}</span>
      <span class="file-name" title="${file.name}">${file.name}</span>
      <span class="file-size">${formatSize(file.size)}</span>
      <button class="icon-btn" data-act="up" ${i === 0 ? "disabled" : ""} title="Sposta su">▲</button>
      <button class="icon-btn" data-act="down" ${i === files.length - 1 ? "disabled" : ""} title="Sposta giù">▼</button>
      <button class="icon-btn" data-act="remove" title="Rimuovi">✕</button>
    `;
    li.querySelector('[data-act="up"]').addEventListener("click", () => move(i, -1));
    li.querySelector('[data-act="down"]').addEventListener("click", () => move(i, 1));
    li.querySelector('[data-act="remove"]').addEventListener("click", () => removeAt(i));
    fileListEl.appendChild(li);
  });
  mergeBtn.disabled = files.length < 2;
  clearBtn.disabled = files.length === 0;
}

// --- File picking: click + drag & drop -------------------------------------

fileInput.addEventListener("change", (e) => {
  addFiles(e.target.files);
  fileInput.value = "";
});

["dragenter", "dragover"].forEach((evt) =>
  dropzone.addEventListener(evt, (e) => { e.preventDefault(); dropzone.classList.add("dragover"); })
);
["dragleave", "drop"].forEach((evt) =>
  dropzone.addEventListener(evt, (e) => { e.preventDefault(); dropzone.classList.remove("dragover"); })
);
dropzone.addEventListener("drop", (e) => {
  if (e.dataTransfer && e.dataTransfer.files) addFiles(e.dataTransfer.files);
});

clearBtn.addEventListener("click", () => { files = []; render(); setStatus(""); });

// --- FFmpeg (loaded lazily on first use) -----------------------------------

async function ensureFFmpeg() {
  if (ffmpeg) return ffmpeg;
  setStatus("Preparazione del motore video… (primo avvio: scarica ~30 MB)", "busy");
  const instance = new FFmpeg();
  instance.on("log", ({ message }) => { logBuffer.push(message); });
  // Tutto caricato come blob di pari-origine: da CDN un Worker cross-origin
  // verrebbe bloccato, mentre un worker-blob può importare il core-blob (ESM).
  await instance.load({
    classWorkerURL: await toBlobURL(WORKER_URL, "text/javascript"),
    coreURL: await toBlobURL(`${CORE_BASE}/ffmpeg-core.js`, "text/javascript"),
    wasmURL: await toBlobURL(`${CORE_BASE}/ffmpeg-core.wasm`, "application/wasm"),
  });
  ffmpeg = instance;
  return ffmpeg;
}

// Run ffmpeg with no output just to read the stream info it prints to the log.
async function probe(name) {
  logBuffer = [];
  try { await ffmpeg.exec(["-i", name]); } catch (_) { /* expected: no output file */ }
  const text = logBuffer.join("\n");

  const vLine = text.split("\n").find((l) => l.includes("Video:")) || "";
  const size = /(\d{2,5})x(\d{2,5})/.exec(vLine);
  if (!size) throw new Error(`Impossibile leggere il video "${name}".`);

  const fpsM = /([\d.]+)\s*fps/.exec(vLine);
  const codecM = /Video:\s*([a-zA-Z0-9_]+)/.exec(vLine);
  const durM = /Duration:\s*(\d+):(\d+):(\d+\.\d+)/.exec(text);
  const duration = durM
    ? (+durM[1]) * 3600 + (+durM[2]) * 60 + parseFloat(durM[3])
    : 0;

  return {
    width: parseInt(size[1], 10),
    height: parseInt(size[2], 10),
    fps: fpsM ? parseFloat(fpsM[1]) : 30,
    vcodec: codecM ? codecM[1] : "unknown",
    duration,
    hasAudio: text.includes("Audio:"),
  };
}

async function fileExists(name) {
  try {
    const data = await ffmpeg.readFile(name);
    return data && data.length > 0;
  } catch (_) {
    return false;
  }
}

// Fast, lossless: works only when all inputs share codec/resolution/fps/audio.
async function tryFastConcat(infos, names, out) {
  const first = infos[0];
  const uniform = infos.every((i) =>
    i.width === first.width && i.height === first.height &&
    i.vcodec === first.vcodec && i.hasAudio === first.hasAudio &&
    Math.abs(i.fps - first.fps) < 0.01
  );
  if (!uniform) return false;

  const list = names.map((n) => `file '${n}'`).join("\n");
  await ffmpeg.writeFile("list.txt", new TextEncoder().encode(list));
  try {
    await ffmpeg.exec(["-y", "-f", "concat", "-safe", "0", "-i", "list.txt",
      "-c", "copy", "-movflags", "+faststart", out]);
  } catch (_) { return false; }
  return fileExists(out);
}

// Robust: normalise every clip to a common canvas and re-encode.
async function reencodeConcat(infos, names, out) {
  const canvasW = even(Math.max(...infos.map((i) => i.width)));
  const canvasH = even(Math.max(...infos.map((i) => i.height)));
  const fps = Math.round(Math.max(...infos.map((i) => i.fps))) || 30;

  const args = ["-y"];
  names.forEach((n) => args.push("-i", n));

  // Add a finite silent-audio input for every clip without audio.
  const silentIndex = {};
  let nextIndex = names.length;
  infos.forEach((info, idx) => {
    if (!info.hasAudio) {
      const dur = Math.max(info.duration, 0.1).toFixed(3);
      args.push("-f", "lavfi", "-t", dur, "-i",
        "anullsrc=channel_layout=stereo:sample_rate=44100");
      silentIndex[idx] = nextIndex++;
    }
  });

  const filters = [];
  const pads = [];
  infos.forEach((info, idx) => {
    filters.push(
      `[${idx}:v]scale=${canvasW}:${canvasH}:force_original_aspect_ratio=decrease,` +
      `pad=${canvasW}:${canvasH}:-1:-1:color=black,setsar=1,fps=${fps},format=yuv420p[v${idx}]`
    );
    const aSrc = info.hasAudio ? idx : silentIndex[idx];
    filters.push(`[${aSrc}:a]aformat=sample_rates=44100:channel_layouts=stereo[a${idx}]`);
    pads.push(`[v${idx}][a${idx}]`);
  });

  const filterComplex =
    filters.join(";") + ";" + pads.join("") + `concat=n=${infos.length}:v=1:a=1[outv][outa]`;

  args.push(
    "-filter_complex", filterComplex,
    "-map", "[outv]", "-map", "[outa]",
    "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
    "-c:a", "aac", "-b:a", "192k",
    "-movflags", "+faststart", out
  );

  await ffmpeg.exec(args);
  if (!(await fileExists(out))) {
    throw new Error("FFmpeg non è riuscito a unire i video.");
  }
}

// --- Save ------------------------------------------------------------------

async function saveBlob(blob) {
  if (typeof window.showSaveFilePicker === "function") {
    try {
      const handle = await window.showSaveFilePicker({
        suggestedName: "video-unito.mp4",
        types: [{ description: "Video MP4", accept: { "video/mp4": [".mp4"] } }],
      });
      const writable = await handle.createWritable();
      await writable.write(blob);
      await writable.close();
      return "saved";
    } catch (err) {
      if (err && err.name === "AbortError") return "cancelled";
    }
  }
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "video-unito.mp4";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
  return "downloaded";
}

// --- Merge orchestration ---------------------------------------------------

async function cleanupFS(names, extra) {
  for (const n of [...names, ...extra]) {
    try { await ffmpeg.deleteFile(n); } catch (_) {}
  }
}

mergeBtn.addEventListener("click", async () => {
  if (files.length < 2) { setStatus("Seleziona almeno 2 file video.", "error"); return; }

  const totalBytes = files.reduce((s, f) => s + f.size, 0);
  if (totalBytes > 700 * 1024 * 1024) {
    setStatus("File troppo grandi per l'elaborazione nel browser (max ~700 MB in totale). Usa la versione desktop.", "error");
    return;
  }

  mergeBtn.disabled = true;
  clearBtn.disabled = true;
  const names = files.map((f, i) => `in${i}.${extOf(f.name)}`);

  try {
    await ensureFFmpeg();

    ffmpeg.on("progress", ({ progress }) => {
      if (progress >= 0 && progress <= 1) setProgress(progress);
    });

    setStatus("Caricamento dei file…", "busy");
    setProgress(0);
    for (let i = 0; i < files.length; i++) {
      await ffmpeg.writeFile(names[i], await fetchFile(files[i]));
    }

    setStatus("Analisi dei video…", "busy");
    const infos = [];
    for (const n of names) infos.push(await probe(n));

    setStatus("Unione in corso… può richiedere qualche minuto.", "busy");
    const fast = await tryFastConcat(infos, names, "out.mp4");
    if (!fast) {
      await reencodeConcat(infos, names, "out.mp4");
    }

    const data = await ffmpeg.readFile("out.mp4");
    const blob = new Blob([data.buffer], { type: "video/mp4" });

    setProgress(null);
    const result = await saveBlob(blob);
    if (result === "cancelled") setStatus("Salvataggio annullato.", "");
    else if (result === "saved") setStatus("✓ Video salvato nella posizione scelta.", "success");
    else setStatus("✓ Video pronto: controlla la cartella Download.", "success");

    await cleanupFS(names, ["out.mp4", "list.txt"]);
  } catch (err) {
    console.error(err);
    setProgress(null);
    setStatus("Errore durante l'unione: " + (err && err.message ? err.message : "riprova con video più piccoli."), "error");
  } finally {
    render();
  }
});

render();
