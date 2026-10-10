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
// Any element with data-tip="<html>" shows a tooltip on hover, or on tap on touch
// screens, where it stays until the next tap elsewhere or a swipe. Inside an
// element with data-near (the map), a tap also finds a small mark next to the finger.

let tooltip;
let lastPointer = "mouse";
const NEAR_PX = 22;

// The [data-tip] mark under the pointer, or for touch the nearest one inside data-near.
function tipTarget(e) {
  const hit = e.target.closest?.("[data-tip]");
  if (hit || lastPointer === "mouse") return hit;
  const box = e.target.closest?.("[data-near]");
  if (!box) return null;
  let best = null;
  let bestDist = NEAR_PX;
  for (const m of box.querySelectorAll("[data-tip]")) {
    const r = m.getBoundingClientRect();
    const d = Math.hypot(e.clientX - (r.left + r.width / 2), e.clientY - (r.top + r.height / 2)) - r.width / 2;
    if (d < bestDist) [best, bestDist] = [m, d];
  }
  return best;
}

export function initTooltip() {
  tooltip = document.getElementById("tooltip");
  document.addEventListener("pointermove", (e) => {
    if (e.pointerType !== "mouse") return;
    const t = e.target.closest?.("[data-tip]");
    if (t) showTooltip(t.dataset.tip, e.clientX, e.clientY);
    else if (!e.target.closest?.("svg[data-hover]")) hideTooltip();
  });
  document.addEventListener("pointerdown", (e) => {
    lastPointer = e.pointerType;
    if (e.pointerType === "mouse") return;
    const t = tipTarget(e);
    if (t) showTooltip(t.dataset.tip, e.clientX, e.clientY);
    else if (!e.target.closest?.("svg[data-hover]")) hideTooltip();
  });
  // A tap that filters the page can shift the layout and fire "scroll" on its own,
  // so on touch screens only a swipe hides the tooltip.
  document.addEventListener("scroll", () => lastPointer === "mouse" && hideTooltip(), { passive: true });
  document.addEventListener("touchmove", hideTooltip, { passive: true });
}

// A tap just next to a small mark inside data-near clicks that mark.
function clickNearest(el) {
  el.addEventListener("click", (e) => {
    if (lastPointer === "mouse" || e.target.closest("[data-key]")) return;
    const t = tipTarget(e);
    if (t?.dataset.key != null) t.dispatchEvent(new MouseEvent("click", { bubbles: true, clientX: e.clientX, clientY: e.clientY }));
  });
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
// One bubble per place on a faint outline of the country, with a slow radar sweep.
// points: [{ key, name, lat, lon, value, tip, selected, label }]

const GEO = { lonMin: 5.7, lonMax: 15.2, latMin: 47.2, latMax: 55.1 };
const KX = Math.cos((51.2 * Math.PI) / 180); // squash longitude at Germany's mid-latitude
const CENTRE = { lon: 10.45, lat: 51.16 }; // geographic centre of Germany, origin of the sweep

// Germany as [lon, lat] rings: the mainland and the larger islands. Natural Earth
// 1:50m (public domain, via world-atlas 2.0.2), simplified to about 3 km.
const DE_OUTLINE = [
  [[9.52,47.52],[9.18,47.67],[8.88,47.66],[8.57,47.78],[8.4,47.69],[8.56,47.62],[8.43,47.59],[7.93,47.56],[7.57,47.61],[7.62,48.16],[7.84,48.64],[8.14,48.89],[8.13,48.97],[7.61,49.06],[7.45,49.15],[7.04,49.11],[7.0,49.18],[6.89,49.21],[6.73,49.16],[6.54,49.4],[6.35,49.45],[6.49,49.8],[6.26,49.87],[6.11,50.09],[6.18,50.23],[6.36,50.32],[6.34,50.45],[6.18,50.52],[6.24,50.6],[5.99,50.75],[6.05,50.91],[5.86,51.03],[6.13,51.15],[6.08,51.22],[6.19,51.41],[5.95,51.8],[6.17,51.88],[6.36,51.82],[6.74,51.91],[6.8,51.98],[6.72,52.08],[7.02,52.27],[7.0,52.42],[6.75,52.46],[6.69,52.53],[6.75,52.63],[7.01,52.63],[7.18,52.97],[7.2,53.28],[7.05,53.38],[7.21,53.66],[8.01,53.69],[8.17,53.54],[8.11,53.47],[8.25,53.45],[8.33,53.61],[8.49,53.51],[8.49,53.39],[8.53,53.78],[8.62,53.88],[8.9,53.84],[9.21,53.86],[9.59,53.6],[9.78,53.55],[9.63,53.6],[9.31,53.86],[8.98,53.93],[8.9,54.0],[8.91,54.26],[8.78,54.31],[8.65,54.29],[8.65,54.4],[8.95,54.47],[8.96,54.54],[8.68,54.79],[8.67,54.9],[8.9,54.9],[9.25,54.81],[9.62,54.85],[9.89,54.78],[10.02,54.67],[10.03,54.58],[9.87,54.47],[10.14,54.49],[10.21,54.41],[10.36,54.44],[10.73,54.32],[11.01,54.38],[11.06,54.28],[11.01,54.18],[10.81,54.08],[10.92,54.0],[11.1,54.01],[11.4,53.95],[11.8,54.14],[12.11,54.17],[12.58,54.47],[13.03,54.41],[13.15,54.28],[13.45,54.14],[13.73,54.15],[13.87,53.85],[14.02,53.77],[14.26,53.73],[14.41,53.22],[14.13,52.88],[14.62,52.53],[14.55,52.36],[14.75,52.08],[14.6,51.83],[14.74,51.63],[14.73,51.52],[14.91,51.46],[15.02,51.25],[14.77,50.82],[14.61,50.86],[14.55,50.99],[14.32,51.04],[14.25,51.0],[14.37,50.9],[13.56,50.7],[13.44,50.6],[13.38,50.62],[13.18,50.51],[13.02,50.49],[12.94,50.41],[12.76,50.43],[12.55,50.39],[12.28,50.18],[12.09,50.3],[12.21,50.1],[12.51,49.9],[12.39,49.74],[12.68,49.41],[12.81,49.33],[12.92,49.33],[13.4,48.98],[13.55,48.96],[13.82,48.77],[13.73,48.54],[13.49,48.58],[13.38,48.36],[12.9,48.2],[12.76,48.11],[12.95,47.89],[12.9,47.72],[13.06,47.66],[13.02,47.48],[12.81,47.54],[12.77,47.64],[12.68,47.67],[12.48,47.64],[12.21,47.72],[12.18,47.62],[11.72,47.58],[11.3,47.42],[11.04,47.39],[10.87,47.52],[10.44,47.55],[10.37,47.37],[10.18,47.28],[10.2,47.36],[10.07,47.39],[9.97,47.5],[9.75,47.58]],
  [[13.71,54.38],[13.71,54.28],[13.48,54.34],[13.42,54.25],[13.19,54.33],[13.18,54.54],[13.34,54.7],[13.42,54.7],[13.49,54.62],[13.66,54.56],[13.58,54.46]],
  [[14.21,53.95],[14.21,53.87],[13.93,53.88],[13.83,54.13]],
  [[8.31,54.79],[8.3,54.91],[8.45,55.05],[8.38,54.9],[8.63,54.89],[8.35,54.85]],
  [[11.28,54.42],[11.13,54.42],[11.01,54.47],[11.04,54.52],[11.23,54.5]],
];

export function bubbleMap(el, points) {
  const W = 420;
  const H = Math.round((W * (GEO.latMax - GEO.latMin)) / ((GEO.lonMax - GEO.lonMin) * KX));
  const px = (lon) => ((lon - GEO.lonMin) / (GEO.lonMax - GEO.lonMin)) * W;
  const py = (lat) => ((GEO.latMax - lat) / (GEO.latMax - GEO.latMin)) * H;
  const max = Math.max(...points.map((p) => p.value), 1);
  const r = (v) => 1.5 + Math.sqrt(v / max) * 18;
  const anySelected = points.some((p) => p.selected);
  // Big bubbles first so small ones stay on top and hoverable.
  const sorted = [...points].filter((p) => p.lat != null && p.value > 0).sort((a, b) => b.value - a.value);

  const land = DE_OUTLINE.map((ring) => `M${ring.map(([lon, lat]) => `${px(lon).toFixed(1)},${py(lat).toFixed(1)}`).join("L")}Z`).join("");
  const cx = px(CENTRE.lon);
  const cy = py(CENTRE.lat);
  const reach = Math.hypot(Math.max(cx, W - cx), Math.max(cy, H - cy));
  // The sweep: a fan of thin wedges that brighten towards the leading edge.
  const SLICES = 12;
  const SPAN = 42; // degrees
  const at = (deg) => `${(cx + reach * Math.sin((deg * Math.PI) / 180)).toFixed(1)},${(cy - reach * Math.cos((deg * Math.PI) / 180)).toFixed(1)}`;
  const fan = Array.from({ length: SLICES }, (_, i) => {
    const a0 = -SPAN + (SPAN / SLICES) * i;
    const a1 = a0 + SPAN / SLICES + 0.3;
    return `<path d="M${cx.toFixed(1)},${cy.toFixed(1)}L${at(a0)}A${reach.toFixed(1)},${reach.toFixed(1)} 0 0 1 ${at(a1)}Z" fill-opacity="${(((i + 1) / SLICES) * 0.16).toFixed(3)}"/>`;
  }).join("");

  if (!el.dataset.near) {
    el.dataset.near = "";
    clickNearest(el);
  }
  el.innerHTML = `<svg class="map" viewBox="-30 -10 ${W + 60} ${H + 20}" role="img" aria-label="Map of Werkstudent postings by place">
    <defs><clipPath id="map-land"><path d="${land}"/></clipPath></defs>
    <path class="map-land" d="${land}"/>
    <g class="map-radar" clip-path="url(#map-land)" aria-hidden="true">
      ${[0.25, 0.5, 0.75].map((f) => `<circle class="map-ring" cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="${(reach * f).toFixed(1)}"/>`).join("")}
      <g class="map-sweep">${fan}<line x1="${cx.toFixed(1)}" y1="${cy.toFixed(1)}" x2="${cx.toFixed(1)}" y2="${(cy - reach).toFixed(1)}"/>
        <animateTransform attributeName="transform" type="rotate" from="0 ${cx.toFixed(1)} ${cy.toFixed(1)}" to="360 ${cx.toFixed(1)} ${cy.toFixed(1)}" dur="12s" repeatCount="indefinite"/>
      </g>
    </g>
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
