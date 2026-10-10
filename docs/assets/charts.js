// Small, dependency-free chart helpers. Everything renders plain HTML/SVG and
// stays interactive: rows and marks carry data-* attributes that the page
// listens to, and every mark has a tooltip (data-tip).

export const fmt = {
  eur: (v) => (v == null ? "—" : `€${v.toFixed(2)}`),
  eur0: (v) => (v == null ? "—" : `€${Math.round(v)}`),
  pct: (v, digits = 1) => (v == null ? "—" : `${(v * 100).toFixed(digits)}%`),
  int: (v) => (v == null ? "—" : Math.round(v).toLocaleString("en-GB")),
  signedPct: (v) => (v == null ? "—" : `${v >= 0 ? "+" : "−"}${Math.abs(v * 100).toFixed(1)}%`),
  date: (iso) =>
    new Date(`${iso}T00:00:00`).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }),
  shortDate: (iso) => new Date(`${iso}T00:00:00`).toLocaleDateString("en-GB", { day: "numeric", month: "short" }),
};

export function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

// --- Tooltip -------------------------------------------------------------------
// Any element with data-tip="<html>" shows a tooltip on hover (or tap on touch).

let tooltip;

export function initTooltip() {
  tooltip = document.getElementById("tooltip");
  document.addEventListener("pointermove", (e) => {
    const t = e.target.closest?.("[data-tip]");
    if (t) showTooltip(t.dataset.tip, e.clientX, e.clientY);
    else if (!e.target.closest?.("svg[data-hover]")) hideTooltip();
  });
  document.addEventListener("pointerdown", (e) => {
    const t = e.target.closest?.("[data-tip]");
    if (t && e.pointerType !== "mouse") showTooltip(t.dataset.tip, e.clientX, e.clientY);
  });
  document.addEventListener("scroll", hideTooltip, { passive: true });
}

export function showTooltip(html, x, y) {
  tooltip.innerHTML = html;
  tooltip.hidden = false;
  const pad = 14;
  const { width, height } = tooltip.getBoundingClientRect();
  let left = x + pad;
  let top = y + pad;
  if (left + width > window.innerWidth - 8) left = x - width - pad;
  if (top + height > window.innerHeight - 8) top = y - height - pad;
  tooltip.style.left = `${Math.max(8, left)}px`;
  tooltip.style.top = `${Math.max(8, top)}px`;
}

export function hideTooltip() {
  if (tooltip) tooltip.hidden = true;
}

// --- Rolling digits ---------------------------------------------------------------
// Spins each digit of el's text up from the digit shown before (or from 0), like
// a counter. Other characters stay put. Skipped under prefers-reduced-motion.

const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");

export function rollDigits(el, from = "") {
  const to = el.textContent;
  if (reducedMotion.matches || !/\d/.test(to)) return;
  const toDigits = to.replace(/\D/g, "");
  const fromDigits = (from || "").replace(/\D/g, "");
  let k = 0;
  let longest = 0;
  const cells = [...to].map((ch) => {
    if (!/\d/.test(ch)) return `<span class="roll">${esc(ch)}</span>`;
    // Line digits up from the right: units with units, tens with tens.
    const prev = fromDigits[fromDigits.length - toDigits.length + k];
    const d = Number(ch);
    const start = prev == null ? 0 : Number(prev);
    const steps = ((d - start + 10) % 10) + (prev == null ? 10 : 0);
    const ms = steps ? 500 + 70 * k : 0;
    k += 1;
    longest = Math.max(longest, ms);
    if (!steps) return `<span class="roll">${ch}</span>`;
    const strip = Array.from({ length: steps + 1 }, (_, i) => `<span>${(start + i) % 10}</span>`).join("");
    return `<span class="roll"><span class="roll-strip" style="--steps:${steps};--ms:${ms}ms">${strip}</span></span>`;
  });
  if (!longest) return;
  el.setAttribute("aria-label", to);
  el.innerHTML = `<span aria-hidden="true">${cells.join("")}</span>`;
  setTimeout(() => {
    if (el.isConnected && el.getAttribute("aria-label") === to) {
      el.textContent = to;
      el.removeAttribute("aria-label");
    }
  }, longest + 100);
}

// --- Horizontal bars -------------------------------------------------------------
// rows: [{ key, label, sub?, value, text, tip?, muted?, selected? }]
// Rows with a key are buttons: the page handles clicks via data-key.

export function barList(el, rows, { max, empty = "No data for this selection.", dim = true } = {}) {
  if (!rows.length) {
    el.innerHTML = `<p class="empty">${esc(empty)}</p>`;
    return;
  }
  const top = max ?? (Math.max(...rows.map((r) => r.value ?? 0), 0) || 1);
  const anySelected = dim && rows.some((r) => r.selected);
  el.innerHTML = `<div class="bars">${rows
    .map((r) => {
      const w = r.value == null ? 0 : Math.max(0.6, (r.value / top) * 100);
      const cls = ["bar-row", r.key != null ? "clickable" : "", r.selected ? "selected" : "", anySelected && !r.selected ? "dimmed" : ""].join(" ");
      const attrs = r.key != null ? `role="button" tabindex="0" data-key="${esc(r.key)}" aria-pressed="${Boolean(r.selected)}"` : "";
      return `<div class="${cls}" ${attrs} ${r.tip ? `data-tip="${esc(r.tip)}"` : ""}>
        <div class="bar-label">${esc(r.label)}${r.sub ? ` <small>${esc(r.sub)}</small>` : ""}</div>
        <div class="bar-cell">
          <div class="bar-track">${r.value == null ? "" : `<div class="bar-fill${r.muted ? " muted" : ""}" style="width:${w}%"></div>`}</div>
          <span class="bar-value">${esc(r.text)}</span>
        </div>
      </div>`;
    })
    .join("")}</div>`;
}

// --- Histogram with a median marker ----------------------------------------------
// bins: [{ label, value, tip, inRange }]; median: { pos (0..bins), label }

export function histogram(el, bins, { median, axisTitle } = {}) {
  const max = Math.max(...bins.map((b) => b.value), 1);
  const marker = median
    ? `<div class="hist-marker" style="left:${(median.pos / bins.length) * 100}%"><span>${esc(median.label)}</span></div>`
    : "";
  el.innerHTML = `
    <div class="hist">
      ${marker}
      <div class="cols">${bins
        .map(
          (b) => `<div class="col" data-tip="${esc(b.tip)}">
            <div class="col-fill${b.inRange ? "" : " soft"}" style="height:${(b.value / max) * 100}%"></div>
          </div>`,
        )
        .join("")}</div>
    </div>
    <div class="col-axis">${bins.map((b) => `<span>${esc(b.label)}</span>`).join("")}</div>
    ${axisTitle ? `<div class="axis-title">${esc(axisTitle)}</div>` : ""}`;
}

// --- Dot-range rows: median dot on a p25–p75 bar, on a shared € scale --------------
// rows: [{ key, label, sub, p25, median, p75, tip, muted, selected }]

export function dotRange(el, rows, { min, max, ticks, empty = "Not enough pay data for this selection." } = {}) {
  if (!rows.length) {
    el.innerHTML = `<p class="empty">${esc(empty)}</p>`;
    return;
  }
  const x = (v) => ((Math.min(Math.max(v, min), max) - min) / (max - min)) * 100;
  const anySelected = rows.some((r) => r.selected);
  el.innerHTML = `
    <div class="dots">
      <div class="dot-row dot-axis" aria-hidden="true">
        <div></div>
        <div class="dot-track">${ticks.map((t) => `<span style="left:${x(t)}%">€${t}</span>`).join("")}</div>
        <div></div>
      </div>
      ${rows
        .map((r) => {
          const cls = ["dot-row", r.key != null ? "clickable" : "", r.selected ? "selected" : "", anySelected && !r.selected ? "dimmed" : "", r.muted ? "muted" : ""].join(" ");
          const attrs = r.key != null ? `role="button" tabindex="0" data-key="${esc(r.key)}" aria-pressed="${Boolean(r.selected)}"` : "";
          return `<div class="${cls}" ${attrs} data-tip="${esc(r.tip)}">
            <div class="bar-label">${esc(r.label)}${r.sub ? ` <small>${esc(r.sub)}</small>` : ""}</div>
            <div class="dot-track">
              ${ticks.map((t) => `<i class="grid" style="left:${x(t)}%"></i>`).join("")}
              <div class="dot-range" style="left:${x(r.p25)}%;width:${Math.max(0.8, x(r.p75) - x(r.p25))}%"></div>
              <div class="dot" style="left:${x(r.median)}%"></div>
            </div>
            <span class="bar-value">${esc(fmt.eur(r.median))}</span>
          </div>`;
        })
        .join("")}
    </div>`;
}

// --- Bubble map of Germany ----------------------------------------------------------
// The country's outline emerges from the postings themselves: one bubble per place.
// points: [{ key, name, lat, lon, value, tip, selected, label }]

const GEO = { lonMin: 5.7, lonMax: 15.2, latMin: 47.2, latMax: 55.1 };
const KX = Math.cos((51.2 * Math.PI) / 180); // squash longitude at Germany's mid-latitude

export function bubbleMap(el, points) {
  const W = 420;
  const H = Math.round((W * (GEO.latMax - GEO.latMin)) / ((GEO.lonMax - GEO.lonMin) * KX));
  const px = (lon) => ((lon - GEO.lonMin) / (GEO.lonMax - GEO.lonMin)) * W;
  const py = (lat) => ((GEO.latMax - lat) / (GEO.latMax - GEO.latMin)) * H;
  const max = Math.max(...points.map((p) => p.value), 1);
  const r = (v) => 2 + Math.sqrt(v / max) * 26;
  const anySelected = points.some((p) => p.selected);
  // Big bubbles first so small ones stay on top and hoverable.
  const sorted = [...points].filter((p) => p.lat != null && p.value > 0).sort((a, b) => b.value - a.value);
  el.innerHTML = `<svg class="map" viewBox="-30 -10 ${W + 60} ${H + 20}" role="img" aria-label="Map of Werkstudent postings by place">
    ${sorted
      .map(
        (p) => `<circle class="bubble${p.selected ? " selected" : ""}${anySelected && !p.selected ? " dimmed" : ""}"
          cx="${px(p.lon).toFixed(1)}" cy="${py(p.lat).toFixed(1)}" r="${r(p.value).toFixed(1)}"
          data-key="${esc(p.key)}" data-tip="${esc(p.tip)}" tabindex="-1"></circle>`,
      )
      .join("")}
    ${sorted
      .filter((p) => p.label)
      .map(
        (p) => `<text class="map-label" x="${(px(p.lon) + r(p.value) + 4).toFixed(1)}" y="${(py(p.lat) + 4).toFixed(1)}">${esc(p.name)}</text>`,
      )
      .join("")}
  </svg>`;
}

// --- Line chart -----------------------------------------------------------------------

function niceStep(range, ticks) {
  const raw = range / ticks;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const norm = raw / mag;
  return (norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10) * mag;
}

export function lineChart(el, dates, values, { format = fmt.int, label = "" } = {}) {
  const pts = dates.map((d, i) => ({ d, v: values[i] })).filter((p) => p.v != null);
  if (!pts.length) {
    el.innerHTML = `<p class="empty">No data yet.</p>`;
    return;
  }

  const draw = () => {
    const W = Math.max(el.clientWidth, 260);
    const H = 180;
    const m = { l: 46, r: 64, t: 12, b: 26 };
    const vs = pts.map((p) => p.v);
    let lo = Math.min(...vs);
    let hi = Math.max(...vs);
    if (hi === lo) {
      const pad = Math.max(Math.abs(hi) * 0.1, 1);
      lo -= pad;
      hi += pad;
    }
    const step = niceStep(hi - lo, 4);
    lo = Math.floor(lo / step) * step;
    hi = Math.ceil(hi / step) * step;
    const x = (i) => (pts.length === 1 ? m.l + (W - m.l - m.r) / 2 : m.l + (i / (pts.length - 1)) * (W - m.l - m.r));
    const y = (v) => m.t + (1 - (v - lo) / (hi - lo)) * (H - m.t - m.b);

    const ticks = [];
    for (let v = lo; v <= hi + step / 2; v += step) ticks.push(v);
    const grid = ticks.map((v) => `<line x1="${m.l}" x2="${W - m.r}" y1="${y(v)}" y2="${y(v)}"></line>`).join("");
    const yLabels = ticks.map((v) => `<text x="${m.l - 8}" y="${y(v) + 4}" text-anchor="end">${esc(format(v))}</text>`).join("");
    const xIdx = pts.length <= 2 ? pts.map((_, i) => i) : [0, Math.floor((pts.length - 1) / 2), pts.length - 1];
    const xLabels = xIdx.map((i) => `<text x="${x(i)}" y="${H - 6}" text-anchor="middle">${esc(fmt.shortDate(pts[i].d))}</text>`).join("");
    const path = pts.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.v).toFixed(1)}`).join("");
    const area = pts.length > 1 ? `${path}L${x(pts.length - 1)},${y(lo)}L${x(0)},${y(lo)}Z` : "";
    const last = pts[pts.length - 1];

    el.innerHTML = `<svg data-hover viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(label)}: latest ${esc(format(last.v))}">
      <g class="grid">${grid}</g>
      <g class="axis">${yLabels}${xLabels}</g>
      ${area ? `<path class="area" d="${area}"></path>` : ""}
      ${pts.length > 1 ? `<path class="line" d="${path}"></path>` : ""}
      <line class="crosshair" x1="0" x2="0" y1="${m.t}" y2="${H - m.b}" visibility="hidden"></line>
      <circle class="end" cx="${x(pts.length - 1)}" cy="${y(last.v)}" r="4"></circle>
      <text class="end-label" x="${x(pts.length - 1) + 8}" y="${y(last.v) + 4}">${esc(format(last.v))}</text>
    </svg>`;

    const svg = el.querySelector("svg");
    const cross = svg.querySelector(".crosshair");
    svg.addEventListener("pointermove", (e) => {
      const rect = svg.getBoundingClientRect();
      const pxv = ((e.clientX - rect.left) / rect.width) * W;
      let best = 0;
      pts.forEach((_, i) => {
        if (Math.abs(x(i) - pxv) < Math.abs(x(best) - pxv)) best = i;
      });
      cross.setAttribute("x1", x(best));
      cross.setAttribute("x2", x(best));
      cross.setAttribute("visibility", "visible");
      showTooltip(`<strong>${esc(fmt.date(pts[best].d))}</strong><br>${esc(label)}: ${esc(format(pts[best].v))}`, e.clientX, e.clientY);
    });
    svg.addEventListener("pointerleave", () => {
      cross.setAttribute("visibility", "hidden");
      hideTooltip();
    });
  };

  draw();
  let width = el.clientWidth;
  new ResizeObserver(() => {
    if (Math.abs(el.clientWidth - width) > 4) {
      width = el.clientWidth;
      draw();
    }
  }).observe(el);
}
