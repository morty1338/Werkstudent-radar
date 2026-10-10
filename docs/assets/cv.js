// CV analysis, entirely in the browser: the file is read on the device, its text
// is matched against the same skill dictionary the pipeline uses for postings
// (exported to data/patterns.json), and the skills found are put into
// "Your skills". Nothing is uploaded or stored.

import { esc } from "./charts.js?v=dev";
import { t } from "./i18n.js?v=dev";

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
  if (file.size > MAX_BYTES) throw new Error(t("cv.too_big"));
  const name = file.name.toLowerCase();
  if (name.endsWith(".txt") || file.type === "text/plain") return file.text();
  const buffer = await file.arrayBuffer();
  if (name.endsWith(".pdf") || file.type === "application/pdf") return pdfText(buffer);
  if (name.endsWith(".docx")) return docxText(buffer);
  throw new Error(t("cv.format"));
}

// --- Analysis ------------------------------------------------------------------------------------

export async function analyse(text) {
  const { skills, majors } = await loadRules();
  const hit = (list) => list.filter((x) => x.rx.some((rx) => rx.test(text)));
  return { skills: hit(skills).map((x) => x.id), majors: hit(majors).map((x) => ({ id: x.id, label: x.label })) };
}

export function initCv(ctx) {
  const { D } = ctx;
  const input = document.getElementById("cv-file");
  const out = document.getElementById("cv-result");

  input.addEventListener("change", () => input.files[0] && run(input.files[0]));
  out.addEventListener("click", (e) => {
    const b = e.target.closest("[data-programme]");
    if (b) {
      ctx.showProgramme?.(b.dataset.programme);
      document.getElementById("programmes").scrollIntoView({ behavior: "smooth" });
    }
  });

  async function run(file) {
    out.textContent = t("cv.reading", { file: file.name });
    try {
      const text = (await fileText(file)).replace(/\s+/g, " ");
      if (text.trim().length < 40) {
        out.textContent = t("cv.no_text", { file: file.name });
        return;
      }
      const found = await analyse(text);
      const idx = found.skills.map((id) => D.skills.findIndex((s) => s.id === id)).filter((i) => i >= 0);
      if (!idx.length) {
        out.textContent = t("cv.no_skills", { file: file.name });
        return;
      }
      ctx.match.setSkills(idx, { fromCv: true });
      const major = found.majors[0];
      out.innerHTML = `${esc(t("cv.found", { n: idx.length }))}${
        major ? `${esc(t("cv.degree"))}<button type="button" class="link-btn" data-programme="${esc(major.id)}">${esc(major.label)}</button>` : ""}`;
    } catch (err) {
      out.textContent = t("cv.error", { file: file.name, msg: err.message });
    } finally {
      input.value = "";
    }
  }
}
