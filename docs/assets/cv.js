// CV analysis, entirely in the browser: the file is read on the device, its text
// is matched against the same skill dictionary the pipeline uses for postings
// (exported to data/patterns.json), and the skills found are put into
// "Your skills". Nothing is uploaded or stored.

import { esc, fmt } from "./charts.js";

const PDFJS = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.10.38";
const MAX_BYTES = 10 * 1024 * 1024;

let rules = null;

async function loadRules() {
  if (!rules) {
    const res = await fetch("data/patterns.json", { cache: "no-cache" });
    if (!res.ok) throw new Error(`patterns.json: HTTP ${res.status}`);
    const data = await res.json();
    const compile = (list) => list.map((x) => ({ id: x.id, label: x.label, rx: x.patterns.map(([src, flags]) => new RegExp(src, flags)) }));
    rules = { skills: compile(data.skills), majors: compile(data.majors) };
  }
  return rules;
}

// --- Text extraction -----------------------------------------------------------------------

async function pdfText(buffer) {
  const pdfjs = await import(`${PDFJS}/pdf.min.mjs`);
  pdfjs.GlobalWorkerOptions.workerSrc = `${PDFJS}/pdf.worker.min.mjs`;
  const doc = await pdfjs.getDocument({ data: buffer }).promise;
  const pages = [];
  for (let p = 1; p <= Math.min(doc.numPages, 20); p++) {
    const content = await (await doc.getPage(p)).getTextContent();
    pages.push(content.items.map((it) => it.str + (it.hasEOL ? "\n" : " ")).join(""));
  }
  return pages.join("\n");
}

// A .docx file is a zip archive; the text lives in word/document.xml.
// Read the zip's central directory and inflate that one entry with the
// browser's built-in DecompressionStream, so no library is needed.
async function docxText(buffer) {
  const view = new DataView(buffer);
  let eocd = -1;
  for (let i = buffer.byteLength - 22; i >= Math.max(0, buffer.byteLength - 66000); i--) {
    if (view.getUint32(i, true) === 0x06054b50) { eocd = i; break; }
  }
  if (eocd < 0) throw new Error("not a valid .docx file");
  const entries = view.getUint16(eocd + 10, true);
  let p = view.getUint32(eocd + 16, true);
  const decoder = new TextDecoder();
  for (let n = 0; n < entries; n++) {
    const method = view.getUint16(p + 10, true);
    const size = view.getUint32(p + 20, true);
    const nameLen = view.getUint16(p + 28, true);
    const extraLen = view.getUint16(p + 30, true);
    const commentLen = view.getUint16(p + 32, true);
    const local = view.getUint32(p + 42, true);
    const name = decoder.decode(new Uint8Array(buffer, p + 46, nameLen));
    if (name === "word/document.xml") {
      const start = local + 30 + view.getUint16(local + 26, true) + view.getUint16(local + 28, true);
      const data = new Uint8Array(buffer, start, size);
      let xml;
      if (method === 0) xml = decoder.decode(data);
      else if (method === 8) xml = await new Response(new Blob([data]).stream().pipeThrough(new DecompressionStream("deflate-raw"))).text();
      else throw new Error("unsupported .docx compression");
      return xml
        .replace(/<\/w:p>|<w:br\/>|<w:tab\/>/g, "\n")
        .replace(/<[^>]+>/g, "")
        .replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&apos;/g, "'");
    }
    p += 46 + nameLen + extraLen + commentLen;
  }
  throw new Error("no text found in the .docx file");
}

async function fileText(file) {
  if (file.size > MAX_BYTES) throw new Error("the file is larger than 10 MB");
  const name = file.name.toLowerCase();
  if (name.endsWith(".txt") || file.type === "text/plain") return file.text();
  const buffer = await file.arrayBuffer();
  if (name.endsWith(".pdf") || file.type === "application/pdf") return pdfText(buffer);
  if (name.endsWith(".docx")) return docxText(buffer);
  throw new Error("please use a PDF, DOCX or TXT file");
}

// --- Analysis ------------------------------------------------------------------------------------

export async function analyse(text) {
  const { skills, majors } = await loadRules();
  const hit = (list) => list.filter((x) => x.rx.some((rx) => rx.test(text)));
  return { skills: hit(skills).map((x) => x.id), majors: hit(majors).map((x) => ({ id: x.id, label: x.label })) };
}

export function initCv(ctx) {
  const { D } = ctx;
  const el = {
    drop: document.getElementById("cv-drop"),
    file: document.getElementById("cv-file"),
    pasteToggle: document.getElementById("cv-paste-toggle"),
    paste: document.getElementById("cv-paste"),
    text: document.getElementById("cv-text"),
    analyse: document.getElementById("cv-analyse"),
    result: document.getElementById("cv-result"),
  };

  el.file.addEventListener("change", () => el.file.files[0] && run(() => fileText(el.file.files[0]), el.file.files[0].name));
  ["dragenter", "dragover"].forEach((t) => el.drop.addEventListener(t, (e) => { e.preventDefault(); el.drop.classList.add("over"); }));
  ["dragleave", "drop"].forEach((t) => el.drop.addEventListener(t, () => el.drop.classList.remove("over")));
  el.drop.addEventListener("drop", (e) => {
    e.preventDefault();
    const f = e.dataTransfer.files[0];
    if (f) run(() => fileText(f), f.name);
  });
  el.pasteToggle.addEventListener("click", () => { el.paste.hidden = !el.paste.hidden; if (!el.paste.hidden) el.text.focus(); });
  el.analyse.addEventListener("click", () => el.text.value.trim() && run(async () => el.text.value, "your text"));
  el.result.addEventListener("click", (e) => {
    const b = e.target.closest("[data-programme]");
    if (b) {
      ctx.showProgramme?.(b.dataset.programme);
      document.getElementById("programmes").scrollIntoView({ behavior: "smooth" });
    }
  });

  async function run(getText, source) {
    el.result.innerHTML = `<p class="cv-sub">Reading ${esc(source)}…</p>`;
    try {
      const text = (await getText()).replace(/\s+/g, " ");
      if (text.trim().length < 40) {
        el.result.innerHTML = `<p class="cv-sub">Couldn't find text in ${esc(source)}. If it's a scanned PDF, paste the text instead.</p>`;
        return;
      }
      const found = await analyse(text);
      const idx = found.skills.map((id) => D.skills.findIndex((s) => s.id === id)).filter((i) => i >= 0);
      if (!idx.length) {
        el.result.innerHTML = `<p class="cv-sub">No skills from our list found in ${esc(source)}. Try adding them by hand below.</p>`;
        return;
      }
      // Strongest = the found skills employers ask for most.
      idx.sort((a, b) => D.skills[b].jobs - D.skills[a].jobs);
      ctx.match.setSkills(idx, { fromCv: true });
      const top = idx.slice(0, 6);
      const total = D.jobs.length;
      const major = found.majors[0];
      el.result.innerHTML = `
        <p class="cv-title">${idx.length} skills found</p>
        <p class="cv-sub">Your strongest, by how many jobs ask for them:</p>
        <div class="bars">${top
          .map((i) => {
            const share = D.skills[i].jobs / total;
            return `<div class="bar-row"><div class="bar-label">${esc(D.skills[i].label)}</div>
              <div class="bar-cell"><div class="bar-track"><div class="bar-fill" style="width:${Math.max(2, (share / (D.skills[top[0]].jobs / total)) * 100)}%"></div></div>
              <span class="bar-value">${fmt.pct(share, share < 0.1 ? 1 : 0)}</span></div></div>`;
          })
          .join("")}</div>
        ${idx.length > top.length ? `<p class="cv-sub" style="margin-top:10px">Also: ${idx.slice(top.length).map((i) => esc(D.skills[i].label)).join(", ")}</p>` : ""}
        ${major ? `<p class="cv-sub">Study programme: <button type="button" class="link-btn" data-programme="${esc(major.id)}">${esc(major.label)} →</button></p>` : ""}
        <p class="cv-sub">They're now in “Your skills”. Your matching jobs are on the right.</p>`;
      document.getElementById("match-summary").scrollIntoView({ behavior: "smooth", block: "nearest" });
    } catch (err) {
      el.result.innerHTML = `<p class="cv-sub">Couldn't read ${esc(source)}: ${esc(err.message)}.</p>`;
    } finally {
      el.file.value = "";
    }
  }
}
