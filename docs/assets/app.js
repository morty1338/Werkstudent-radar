import { barList, columns, esc, fmt, initTooltip, lineChart } from "./charts.js";
import { initChecker } from "./checker.js";

const GERMAN = {
  none: { label: "Not needed", desc: "English posting or “English only”", color: "var(--de-none)" },
  plus: { label: "A plus", desc: "“von Vorteil”, “nice to have”", color: "var(--de-plus)" },
  implicit: { label: "Not mentioned", desc: "German posting, so needed in practice", color: "var(--de-implicit)" },
  required: { label: "Required", desc: "“fließend”, “C1”, “sehr gute Deutschkenntnisse”", color: "var(--de-required)" },
};
const MAJOR_ORDER = ["wiinf", "inf", "bwl", "wiing", "mb", "et", "math", "comm"];
const LIST_PAGE = 12;

async function load(name) {
  const res = await fetch(`data/${name}.json`, { cache: "no-cache" });
  if (!res.ok) throw new Error(`${name}.json: HTTP ${res.status}`);
  return res.json();
}

async function main() {
  initTooltip();
  let summary, checker, history;
  try {
    [summary, checker, history] = await Promise.all([load("summary"), load("checker"), load("history")]);
  } catch (e) {
    document.getElementById("tiles").innerHTML = `<p class="stale">Couldn't load the data (${esc(e.message)}). Please try again later.</p>`;
    return;
  }

  const catLabel = Object.fromEntries(summary.categories.map((c) => [c.key, c.label]));
  const skillLabel = Object.fromEntries(summary.skills.map((s) => [s.id, s.label]));
  const labels = {
    category: (k) => catLabel[k] ?? (k === "other" ? "Other" : k),
    skill: (id) => skillLabel[id] ?? id,
  };

  renderHero(summary);
  renderPay(summary, labels);
  renderGerman(summary, labels);
  renderSkills(summary, checker, labels);
  initChecker(checker, labels);
  renderMajors(summary, labels);
  renderTrends(history);

  // The sections only get their height once the data is rendered, so the
  // browser's own jump to #anchor on load lands in the wrong place.
  const target = location.hash && document.getElementById(location.hash.slice(1));
  if (target) target.scrollIntoView({ behavior: "instant" });
}

// --- Hero ------------------------------------------------------------------------

function renderHero(s) {
  const t = s.totals;
  const tiles = [
    { label: "Werkstudent postings online", value: fmt.int(t.jobs), sub: `from ${fmt.int(t.companies)} employers in ${fmt.int(t.cities)} places` },
    { label: "Median hourly pay", value: fmt.eur(t.median_pay), sub: `middle half ${fmt.eur(t.p25_pay)}–${fmt.eur(t.p75_pay)} · ${fmt.int(t.with_pay)} roles` },
    { label: "Open without German", value: fmt.pct(t.no_german_share), sub: `${fmt.int(t.no_german)} postings` },
    { label: "Typical hours", value: `${t.median_hours ?? "—"} h`, sub: `per week, median of ${fmt.int(t.with_hours)} postings that say` },
  ];
  document.getElementById("tiles").innerHTML = tiles
    .map((x) => `<div class="tile"><div class="label">${esc(x.label)}</div><div class="value">${esc(x.value)}</div><div class="sub">${esc(x.sub)}</div></div>`)
    .join("");
  document.getElementById("asof").textContent =
    `Data as of ${fmt.date(s.as_of)} · ${fmt.int(t.published_7d)} postings first published in the last 7 days · source: Bundesagentur für Arbeit`;

  const ageDays = Math.floor((Date.now() - new Date(`${s.as_of}T12:00:00`)) / 864e5);
  if (ageDays > 2) {
    const stale = document.getElementById("stale");
    stale.textContent = `The daily update hasn't run for ${ageDays} days, so these numbers may be out of date.`;
    stale.hidden = false;
  }
}

// --- Pay -----------------------------------------------------------------------------

function payTip(name, r, max) {
  const lines = [`<strong>${esc(name)}</strong>`];
  lines.push(r.median_pay == null ? "Not enough pay data" : `Median ${fmt.eur(r.median_pay)}/h`);
  lines.push(`${fmt.int(r.with_pay)} roles with pay from ${fmt.int(r.pay_employers ?? 0)} employers`);
  if ((r.top_employer_share ?? 0) > max) lines.push(`${fmt.pct(r.top_employer_share, 0)} of the pay data comes from one employer`);
  lines.push(`${fmt.int(r.jobs)} postings in total`);
  return lines.join("<br>");
}

function renderPay(s, labels) {
  const t = s.totals;
  const ins = s.insights;
  const maxShare = s.thresholds.max_employer_share;
  const parts = [
    `Only ${fmt.pct(t.postings_with_pay / t.jobs, 0)} of postings state an hourly rate. Among those, half pay between ${fmt.eur(t.p25_pay)} and ${fmt.eur(t.p75_pay)}.`,
  ];
  if (ins.best_paid_category && ins.lowest_paid_category) {
    parts.push(
      `${labels.category(ins.best_paid_category.key)} pays most (${fmt.eur(ins.best_paid_category.median_pay)}), ${labels.category(ins.lowest_paid_category.key).toLowerCase()} least (${fmt.eur(ins.lowest_paid_category.median_pay)}).`,
    );
  }
  if (ins.it_vs_marketing) {
    const p = ins.it_vs_marketing.premium;
    parts.push(
      `IT pays ${Math.abs(p) < 0.005 ? "about the same as" : `${fmt.pct(Math.abs(p), 0)} ${p > 0 ? "more" : "less"} than`} marketing (${fmt.eur(ins.it_vs_marketing.it)} vs ${fmt.eur(ins.it_vs_marketing.marketing)}): Werkstudent pay is flatter than full-time pay.`,
    );
  }
  document.getElementById("pay-lede").textContent = parts.join(" ");

  const bins = s.pay_histogram.map((b) => ({
    label: b.bin >= 25 ? "25+" : String(b.bin),
    value: b.jobs,
    tip: `<strong>${b.bin >= 25 ? "€25 or more" : `€${b.bin}.00–${b.bin}.99`}</strong><br>${b.jobs} roles`,
  }));
  columns(document.getElementById("pay-hist"), bins, { axisTitle: "€ per hour" });

  const fieldRows = [...s.categories]
    .sort((a, b) => (b.median_pay ?? -1) - (a.median_pay ?? -1) || b.jobs - a.jobs)
    .map((c) => ({
      label: c.label,
      value: c.median_pay,
      text: c.median_pay == null ? `n=${c.with_pay}` : fmt.eur(c.median_pay),
      tip: payTip(c.label, c, maxShare),
      muted: (c.top_employer_share ?? 0) > maxShare,
    }));
  barList(document.getElementById("pay-fields"), fieldRows);

  const priced = s.cities.filter((c) => c.median_pay != null).sort((a, b) => b.median_pay - a.median_pay || b.jobs - a.jobs);
  const unpriced = s.cities.filter((c) => c.median_pay == null);
  const cityRows = priced.map((c) => {
    const flagged = (c.top_employer_share ?? 0) > maxShare;
    return {
      label: c.city + (flagged ? " †" : ""),
      sub: `${fmt.int(c.jobs)} jobs`,
      value: c.median_pay,
      text: c.median_pay == null ? `n=${c.with_pay}` : fmt.eur(c.median_pay),
      tip: payTip(c.city, c, maxShare),
      muted: flagged,
    };
  });
  barList(document.getElementById("pay-cities"), cityRows);
  if (unpriced.length) {
    document.getElementById("pay-cities").insertAdjacentHTML(
      "beforeend",
      `<p class="hint" style="margin-top:12px">Too little pay data: ${unpriced.map((c) => esc(c.city)).join(", ")}.</p>`,
    );
  }
}

// --- German ---------------------------------------------------------------------------

function renderGerman(s, labels) {
  const t = s.totals;
  const ins = s.insights;
  const it = s.categories.filter((c) => c.key === "it" || c.key === "data");
  const itJobs = it.reduce((a, c) => a + c.jobs, 0);
  const itOpen = it.reduce((a, c) => a + c.no_german, 0);
  const parts = [
    `Only ${fmt.pct(t.no_german_share)} of Werkstudent postings (${fmt.int(t.no_german)}) can be done without German, and only ${fmt.int(t.english_postings)} are written in English.`,
    `Even in IT and data it's ${fmt.int(itOpen)} of ${fmt.int(itJobs)} postings.`,
  ];
  if (ins.berlin) parts.push(`In Berlin: ${fmt.int(ins.berlin.no_german)} of ${fmt.int(ins.berlin.jobs)}.`);
  document.getElementById("german-lede").textContent = parts.join(" ");

  const total = s.german.reduce((a, g) => a + g.jobs, 0);
  document.getElementById("german-stack").innerHTML = `
    <div class="stack" role="img" aria-label="${s.german.map((g) => `${GERMAN[g.key]?.label}: ${fmt.pct(g.share)}`).join(", ")}">
      ${s.german
        .map(
          (g) => `<div style="flex:${g.jobs};background:${GERMAN[g.key]?.color}"
            data-tip="<strong>${esc(GERMAN[g.key]?.label)}</strong><br>${fmt.int(g.jobs)} postings (${fmt.pct(g.share)})<br>${esc(GERMAN[g.key]?.desc)}"></div>`,
        )
        .join("")}
    </div>
    <div class="legend">${s.german
      .map(
        (g) => `<div class="legend-item"><span class="swatch" style="background:${GERMAN[g.key]?.color}"></span>
          <span>${esc(GERMAN[g.key]?.label)} <strong>${fmt.pct(g.share)}</strong> <span class="desc">${esc(GERMAN[g.key]?.desc)}</span></span></div>`,
      )
      .join("")}</div>
    <p class="hint">${fmt.int(total)} postings with a readable text.</p>`;

  const rows = [...s.categories]
    .filter((c) => c.jobs >= 40)
    .sort((a, b) => b.no_german_share - a.no_german_share || b.jobs - a.jobs)
    .map((c) => ({
      label: c.label,
      value: c.no_german_share,
      text: `${fmt.pct(c.no_german_share)} (${c.no_german})`,
      tip: `<strong>${esc(c.label)}</strong><br>${c.no_german} of ${fmt.int(c.jobs)} postings open to non-German speakers`,
    }));
  barList(document.getElementById("german-fields"), rows);

  // List of postings that don't need German
  const list = s.english_friendly;
  const search = document.getElementById("ef-search");
  const field = document.getElementById("ef-field");
  const more = document.getElementById("ef-more");
  const box = document.getElementById("ef-list");
  [...new Set(list.map((j) => j.category))]
    .sort((a, b) => labels.category(a).localeCompare(labels.category(b)))
    .forEach((k) => field.add(new Option(labels.category(k), k)));
  document.getElementById("ef-title").textContent = `All ${list.length} postings open to non-German speakers`;
  let expanded = false;

  const render = () => {
    const q = search.value.trim().toLowerCase();
    const hits = list.filter(
      (j) => (!field.value || j.category === field.value) && (!q || `${j.title} ${j.company} ${j.city}`.toLowerCase().includes(q)),
    );
    const shown = expanded || q ? hits : hits.slice(0, LIST_PAGE);
    box.innerHTML = shown.length
      ? shown.map((j) => jobRow(j, labels)).join("")
      : `<p class="empty">No postings match.</p>`;
    more.hidden = expanded || q || hits.length <= LIST_PAGE;
    more.textContent = `Show all ${hits.length}`;
  };
  search.addEventListener("input", render);
  field.addEventListener("change", render);
  more.addEventListener("click", () => {
    expanded = true;
    render();
  });
  render();
}

function jobRow(j, labels) {
  const g = GERMAN[j.german];
  return `<div class="job">
    <a href="${esc(j.url)}" target="_blank" rel="noopener">${esc(j.title)}</a>
    <div class="meta">${esc(j.company)} · ${esc(j.city || "—")} · ${esc(labels.category(j.category))}</div>
    <div class="side">
      ${g ? `<span class="badge${j.german === "none" || j.german === "plus" ? " strong" : ""}">German: ${esc(g.label.toLowerCase())}</span>` : ""}
      ${j.pay != null ? `<span class="pay">${fmt.eur(j.pay)}/h</span>` : ""}
    </div>
  </div>`;
}

// --- Skills ---------------------------------------------------------------------------

function renderSkills(s, checker, labels) {
  const top = s.skills.slice(0, 2);
  const prog = s.skills.find((x) => x.group === "Programming");
  const data = s.skills.find((x) => x.group === "Data & AI");
  const parts = [`${top[0].label} is asked for in ${fmt.pct(top[0].share, 0)} of postings, ${top[1].label} in ${fmt.pct(top[1].share, 0)}.`];
  if (prog) parts.push(`The most requested programming language is ${prog.label} (${fmt.pct(prog.share)}).`);
  if (data) parts.push(`In data, ${data.label} leads (${fmt.pct(data.share)}).`);
  document.getElementById("skills-lede").textContent = parts.join(" ");

  const field = document.getElementById("sk-field");
  const city = document.getElementById("sk-city");
  checker.categories.forEach((c, i) => field.add(new Option(labels.category(c), i)));
  checker.cities.forEach((c, i) => city.add(new Option(c, i)));

  const render = () => {
    const f = field.value === "" ? null : Number(field.value);
    const c = city.value === "" ? null : Number(city.value);
    const pool = checker.jobs.filter((j) => (f == null || j[0] === f) && (c == null || j[1] === c));
    const counts = new Array(checker.skills.length).fill(0);
    pool.forEach((j) => j[4].forEach((i) => counts[i]++));
    const rows = counts
      .map((n, i) => ({ n, i }))
      .filter((x) => x.n > 0)
      .sort((a, b) => b.n - a.n)
      .slice(0, 20)
      .map(({ n, i }) => ({
        label: checker.skills[i].label,
        sub: checker.skills[i].group,
        value: n / pool.length,
        text: fmt.pct(n / pool.length),
        tip: `<strong>${esc(checker.skills[i].label)}</strong><br>${fmt.int(n)} of ${fmt.int(pool.length)} postings`,
      }));
    document.getElementById("sk-hint").textContent = `Share of ${fmt.int(pool.length)} postings that mention the skill.`;
    barList(document.getElementById("sk-bars"), rows);
  };
  field.addEventListener("change", render);
  city.addEventListener("change", render);
  render();

  const overall = s.totals.median_pay;
  const maxShare = s.thresholds.max_employer_share;
  const paid = s.skills
    .filter((x) => x.median_pay != null && (x.top_employer_share ?? 1) <= maxShare)
    .map((x) => ({ ...x, premium: x.median_pay / overall - 1 }))
    .filter((x) => x.premium > 0)
    .sort((a, b) => b.premium - a.premium || b.with_pay - a.with_pay)
    .slice(0, 12);
  barList(
    document.getElementById("sk-pay"),
    paid.map((x) => ({
      label: x.label,
      value: x.premium,
      text: `${fmt.eur(x.median_pay)} (${fmt.signedPct(x.premium)})`,
      tip: `<strong>${esc(x.label)}</strong><br>Median ${fmt.eur(x.median_pay)}/h vs ${fmt.eur(overall)} overall<br>${x.with_pay} roles with pay from ${x.pay_employers} employers`,
    })),
  );
}

// --- Study programmes ----------------------------------------------------------------

function renderMajors(s, labels) {
  const majors = [...s.majors].sort((a, b) => MAJOR_ORDER.indexOf(a.id) - MAJOR_ORDER.indexOf(b.id));
  const tabs = document.getElementById("mj-tabs");
  const panel = document.getElementById("mj-panel");
  const fromHash = new URLSearchParams(location.search).get("programme");
  let current = majors.find((m) => m.id === fromHash) ? fromHash : majors[0].id;

  tabs.innerHTML = majors
    .map((m) => `<button type="button" class="tab" role="tab" data-id="${m.id}" aria-controls="mj-panel">${esc(m.label)}</button>`)
    .join("");
  tabs.addEventListener("click", (e) => {
    const b = e.target.closest(".tab");
    if (!b) return;
    current = b.dataset.id;
    render();
  });

  const render = () => {
    tabs.querySelectorAll(".tab").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.id === current)));
    const m = majors.find((x) => x.id === current);
    panel.innerHTML = `
      <div class="mj-stats">
        <div class="mj-stat"><div class="label">Postings mentioning it</div><div class="value">${fmt.int(m.jobs)}</div></div>
        <div class="mj-stat"><div class="label">Share of all postings</div><div class="value">${fmt.pct(m.share, 0)}</div></div>
        <div class="mj-stat"><div class="label">Median pay</div><div class="value">${fmt.eur(m.median_pay)}</div></div>
        <div class="mj-stat"><div class="label">Open without German</div><div class="value">${fmt.pct(m.no_german_share)}</div></div>
      </div>
      <div class="mj-grid">
        <div><h3>Fields</h3><div id="mj-fields"></div></div>
        <div>
          <h3>Most requested skills</h3>
          <div class="tag-list">${m.skills.map((x) => `<span class="badge">${esc(labels.skill(x.key))} · ${x.jobs}</span>`).join("")}</div>
          <h3 style="margin-top:18px">Top cities</h3>
          <div class="tag-list">${m.cities.map((x) => `<span class="badge">${esc(x.key)} · ${x.jobs}</span>`).join("")}</div>
        </div>
      </div>
      <h3 style="margin:22px 0 4px">Latest postings</h3>
      <div class="job-list">${m.examples.map((j) => jobRow(j, labels)).join("")}</div>`;
    barList(
      panel.querySelector("#mj-fields"),
      m.categories.map((c) => ({
        label: labels.category(c.key),
        value: c.jobs,
        text: fmt.int(c.jobs),
        tip: `<strong>${esc(labels.category(c.key))}</strong><br>${c.jobs} postings mention ${esc(m.label)}`,
      })),
    );
  };
  render();
}

// --- Trends ---------------------------------------------------------------------------------

function renderTrends(h) {
  const days = h.dates.length;
  const lede = document.getElementById("trends-lede");
  lede.textContent =
    days < 7
      ? `Daily snapshots started on ${fmt.date(h.dates[0])} (${days} day${days === 1 ? "" : "s"} so far). Which postings are online on a given day can't be reconstructed later, so this history only exists because it's recorded every morning. Give it a few weeks to show how demand and pay move, for example around the start of a semester.`
      : `${days} daily snapshots since ${fmt.date(h.dates[0])}.`;
  lineChart(document.getElementById("tr-jobs"), h.dates, h.series["total:all:jobs"], { label: "Postings", format: fmt.int });
  lineChart(document.getElementById("tr-pay"), h.dates, h.series["total:all:median_pay"], { label: "Median pay", format: fmt.eur });
}

main();
