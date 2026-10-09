// Small, dependency-free chart helpers: bar lists, a column histogram, a line
// chart and one shared tooltip. Everything renders plain HTML/SVG.

export const fmt = {
  eur: (v) => (v == null ? "—" : `€${v.toFixed(2)}`),
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
// Any element with data-tip="<html>" shows a tooltip on hover or tap.

let tooltip;

export function initTooltip() {
  tooltip = document.getElementById("tooltip");
  const show = (target, x, y) => {
    tooltip.innerHTML = target.dataset.tip;
    tooltip.hidden = false;
    place(x, y);
  };
  document.addEventListener("pointermove", (e) => {
    const t = e.target.closest("[data-tip]");
    if (t) show(t, e.clientX, e.clientY);
    else if (!e.target.closest("svg[data-hover]")) hideTooltip();
  });
  document.addEventListener("pointerdown", (e) => {
    const t = e.target.closest("[data-tip]");
    if (t && e.pointerType !== "mouse") show(t, e.clientX, e.clientY);
  });
  document.addEventListener("scroll", hideTooltip, { passive: true });
}

export function showTooltip(html, x, y) {
  tooltip.innerHTML = html;
  tooltip.hidden = false;
  place(x, y);
}

export function hideTooltip() {
  if (tooltip) tooltip.hidden = true;
}

function place(x, y) {
  const pad = 12;
  const { width, height } = tooltip.getBoundingClientRect();
  let left = x + pad;
  let top = y + pad;
  if (left + width > window.innerWidth - 8) left = x - width - pad;
  if (top + height > window.innerHeight - 8) top = y - height - pad;
  tooltip.style.left = `${Math.max(8, left)}px`;
  tooltip.style.top = `${Math.max(8, top)}px`;
}

// --- Horizontal bars -------------------------------------------------------------
// rows: [{ label, sub?, value, text, tip?, muted? }]; bars start at zero.

export function barList(el, rows, { max } = {}) {
  if (!rows.length) {
    el.innerHTML = `<p class="empty">No data for this selection.</p>`;
    return;
  }
  const top = max ?? (Math.max(...rows.map((r) => r.value ?? 0), 0) || 1);
  el.innerHTML = `<div class="bars">${rows
    .map((r) => {
      const w = r.value == null ? 0 : Math.max(0.5, (r.value / top) * 100);
      return `<div class="bar-row" ${r.tip ? `data-tip="${esc(r.tip)}"` : ""}>
        <div class="bar-label" title="${esc(r.label)}">${esc(r.label)}${r.sub ? ` <small>${esc(r.sub)}</small>` : ""}</div>
        <div class="bar-cell">
          <div class="bar-track">${r.value == null ? "" : `<div class="bar-fill${r.muted ? " muted" : ""}" style="width:${w}%"></div>`}</div>
          <span class="bar-value${r.value == null ? " na" : ""}">${esc(r.text)}</span>
        </div>
      </div>`;
    })
    .join("")}</div>`;
}

// --- Column histogram -------------------------------------------------------------
// bins: [{ label, value, tip }]

export function columns(el, bins, { axisTitle } = {}) {
  const max = Math.max(...bins.map((b) => b.value), 1);
  el.innerHTML = `
    <div class="cols">${bins
      .map(
        (b) => `<div class="col" data-tip="${esc(b.tip)}">
          <span class="col-value">${b.value || ""}</span>
          <div class="col-fill" style="height:${(b.value / max) * 85}%"></div>
        </div>`,
      )
      .join("")}</div>
    <div class="col-axis">${bins.map((b) => `<span>${esc(b.label)}</span>`).join("")}</div>
    ${axisTitle ? `<div class="axis-title">${esc(axisTitle)}</div>` : ""}`;
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
    const H = 200;
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
    const grid = ticks
      .map((v) => `<line x1="${m.l}" x2="${W - m.r}" y1="${y(v)}" y2="${y(v)}"></line>`)
      .join("");
    const yLabels = ticks
      .map((v) => `<text x="${m.l - 8}" y="${y(v) + 4}" text-anchor="end">${esc(format(v))}</text>`)
      .join("");
    const xIdx = pts.length <= 2 ? pts.map((_, i) => i) : [0, Math.floor((pts.length - 1) / 2), pts.length - 1];
    const xLabels = xIdx
      .map((i) => `<text x="${x(i)}" y="${H - 6}" text-anchor="middle">${esc(fmt.shortDate(pts[i].d))}</text>`)
      .join("");
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
      const r = svg.getBoundingClientRect();
      const px = ((e.clientX - r.left) / r.width) * W;
      let best = 0;
      pts.forEach((_, i) => {
        if (Math.abs(x(i) - px) < Math.abs(x(best) - px)) best = i;
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
