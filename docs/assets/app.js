import { barList, bubbleMap, dotRange, esc, fmt, histogram, initTooltip, lineChart, rollDigits } from "./charts.js?v=dev";
import { initCv } from "./cv.js?v=dev";
import { initMatch } from "./match.js?v=dev";

// Column positions in checker.json "jobs" rows.
export const J = { CAT: 0, CITY: 1, DE: 2, PAY: 3, SKILLS: 4, ROLE: 5, ROLE_CITY: 6, COMPANY: 7 };
const MAJOR_ORDER = ["wiinf", "inf", "bwl", "wiing", "mb", "et", "math", "comm"];
const PAY_MIN = 12;
const PAY_BINS = 14; // €12 … €24, then 25+

async function load(name) {
  const res = await fetch(`data/${name}.json`, { cache: "no-cache" });
  if (!res.ok) throw new Error(`${name}.json: HTTP ${res.status}`);
  return res.json();
}

function quantile(sorted, q) {
  if (!sorted.length) return null;
  const pos = (sorted.length - 1) * q;
  const lo = Math.floor(pos);
  const hi = Math.min(lo + 1, sorted.length - 1);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo);
}

async function main() {
  initTooltip();
  let S, D, H;
  try {
    [S, D, H] = await Promise.all([load("summary"), load("checker"), load("history")]);
  } catch (e) {
    document.getElementById("tiles").innerHTML = `<p class="stale">Couldn't load the data (${esc(e.message)}). Please try again later.</p>`;
    return;
  }

  const params = new URLSearchParams(location.search);
  const state = {
    field: Math.max(-1, D.categories.indexOf(params.get("field"))),
    city: Math.max(-1, D.cities.findIndex((c) => c.name === params.get("city"))),
    noGerman: params.get("german") === "no",
    payBy: "field",
    skillGroup: "All",
    skill: null,
  };

  const catLabel = (i) => (i < 0 ? "Other" : D.category_labels[D.categories[i]] ?? D.categories[i]);
  const skillLabel = (id) => D.skills.find((s) => s.id === id)?.label ?? S.skills.find((s) => s.id === id)?.label ?? id;

  // Postings that pass the filters; `except` drops one filter so a chart can show
  // the distribution over that dimension with the current choice highlighted.
  function pool(except = {}) {
    const out = [];
    D.jobs.forEach((j, i) => {
      if (!except.field && state.field >= 0 && j[J.CAT] !== state.field) return;
      if (!except.city && state.city >= 0 && j[J.CITY] !== state.city) return;
      if (state.noGerman && j[J.DE] > 1) return;
      out.push(i);
    });
    return out;
  }

  // Pay counts each role once (per city when looking at one city), as in the SQL step.
  function payStats(idx, perCity = state.city >= 0) {
    const flag = perCity ? J.ROLE_CITY : J.ROLE;
    const values = [];
    const byCompany = new Map();
    for (const i of idx) {
      const j = D.jobs[i];
      if (j[J.PAY] == null || !j[flag]) continue;
      values.push(j[J.PAY]);
      byCompany.set(j[J.COMPANY], (byCompany.get(j[J.COMPANY]) || 0) + 1);
    }
    values.sort((a, b) => a - b);
    const top = Math.max(0, ...byCompany.values());
    return {
      n: values.length,
      values,
      p25: quantile(values, 0.25),
      median: quantile(values, 0.5),
      p75: quantile(values, 0.75),
      employers: byCompany.size,
      topShare: values.length ? top / values.length : 0,
      enough: values.length >= D.min_pay_sample && byCompany.size >= 5,
    };
  }

  const ctx = { D, S, J, state, pool, payStats, catLabel, skillLabel, render: () => render(), syncUrl: () => syncUrl() };

  // --- Filter bar -------------------------------------------------------------------
  const fField = document.getElementById("f-field");
  const fCity = document.getElementById("f-city");
  const fDe = document.getElementById("f-nogerman");
  const fReset = document.getElementById("f-reset");
  const byCount = D.categories.map((_, i) => i).sort((a, b) => countBy(J.CAT, a) - countBy(J.CAT, b)).reverse();
  function countBy(col, v) {
    return D.jobs.reduce((n, j) => n + (j[col] === v), 0);
  }
  byCount.forEach((i) => fField.add(new Option(catLabel(i), i)));
  const TOP_CITIES = 40;
  D.cities.slice(0, TOP_CITIES).forEach((c, i) => fCity.add(new Option(c.name, i)));

  function setField(i) {
    state.field = state.field === i ? -1 : i;
    render();
  }
  function setCity(i) {
    state.city = state.city === i ? -1 : i;
    render();
  }
  ctx.setField = setField;
  ctx.setCity = setCity;

  fField.addEventListener("change", () => { state.field = fField.value === "" ? -1 : Number(fField.value); render(); });
  fCity.addEventListener("change", () => { state.city = fCity.value === "" ? -1 : Number(fCity.value); render(); });
  fDe.addEventListener("change", () => { state.noGerman = fDe.checked; render(); });
  fReset.addEventListener("click", () => { Object.assign(state, { field: -1, city: -1, noGerman: false }); render(); });

  function renderFilters(all) {
    if (state.city >= TOP_CITIES && ![...fCity.options].some((o) => Number(o.value) === state.city)) {
      fCity.add(new Option(D.cities[state.city].name, state.city));
    }
    fField.value = state.field >= 0 ? String(state.field) : "";
    fCity.value = state.city >= 0 ? String(state.city) : "";
    fDe.checked = state.noGerman;
    fField.classList.toggle("active", state.field >= 0);
    fCity.classList.toggle("active", state.city >= 0);
    fReset.hidden = state.field < 0 && state.city < 0 && !state.noGerman;
    document.getElementById("f-count").textContent = `${fmt.int(all.length)} jobs`;
  }

  // Clicks and Enter/Space on any data-key row inside a container.
  function onPick(el, fn) {
    el.addEventListener("click", (e) => {
      const t = e.target.closest("[data-key]");
      if (t) fn(Number(t.dataset.key));
    });
    el.addEventListener("keydown", (e) => {
      const t = e.target.closest("[data-key]");
      if (t && (e.key === "Enter" || e.key === " ")) {
        e.preventDefault();
        fn(Number(t.dataset.key));
      }
    });
  }
  onPick(document.getElementById("map"), setCity);
  onPick(document.getElementById("fields"), setField);
  onPick(document.getElementById("pay-range"), (k) => (state.payBy === "field" ? setField(k) : setCity(k)));
  onPick(document.getElementById("skill-bars"), (k) => { state.skill = k; renderSkills(); });
  document.getElementById("pay-seg").addEventListener("click", (e) => {
    const b = e.target.closest("[data-by]");
    if (!b) return;
    state.payBy = b.dataset.by;
    renderPay();
  });
  document.getElementById("skill-groups").addEventListener("click", (e) => {
    const b = e.target.closest("[data-group]");
    if (!b) return;
    state.skillGroup = b.dataset.group;
    state.skill = null;
    renderSkills();
  });

  // --- Overview tiles ------------------------------------------------------------------
  function renderTiles(all) {
    const ps = payStats(all);
    const places = new Set(all.map((i) => D.jobs[i][J.CITY]).filter((c) => c >= 0)).size;
    const top = topSkills(all)[0];
    const perCity = new Map();
    for (const i of all) {
      const c = D.jobs[i][J.CITY];
      if (c >= 0) perCity.set(c, (perCity.get(c) || 0) + 1);
    }
    const [bigCity, bigCount] = [...perCity].sort((a, b) => b[1] - a[1])[0] ?? [-1, 0];
    const where = [state.field >= 0 ? catLabel(state.field) : null, state.city >= 0 ? D.cities[state.city].name : null].filter(Boolean).join(" · ");
    const tiles = [
      { href: "#where", label: where ? `Jobs · ${where}` : "Werkstudent jobs online", value: fmt.int(all.length), sub: `in ${fmt.int(places)} ${places === 1 ? "place" : "places"}` },
      { href: "#pay", label: "Median pay", value: ps.enough ? fmt.eur(ps.median) : "—", sub: ps.enough ? `per hour · half earn ${fmt.eur0(ps.p25)}–${fmt.eur0(ps.p75)}` : "too few rates stated" },
      { href: "#skills", label: "Most asked-for skill", value: top ? top.label : "—", sub: top ? `in ${fmt.pct(top.share, 0)} of jobs` : "", small: true },
      { href: "#where", label: "Most jobs in", value: bigCity >= 0 ? D.cities[bigCity].name : "—", sub: bigCity >= 0 ? `${fmt.int(bigCount)} jobs` : "", small: true },
    ];
    const box = document.getElementById("tiles");
    const before = [...box.querySelectorAll(".value")].map((v) => v.dataset.value);
    box.innerHTML = tiles
      .map((t) => `<a class="tile${t.cta ? " cta" : ""}" href="${t.href}">
        <span class="label">${esc(t.label)}</span>
        <span class="value" data-value="${esc(t.value)}"${t.small ? ' style="font-size:30px"' : ""}>${esc(t.value)}</span>
        <span class="sub">${esc(t.sub)}</span></a>`)
      .join("");
    // Roll only the numbers that changed (all of them on first load).
    box.querySelectorAll(".value").forEach((v, k) => {
      if (v.dataset.value !== before[k]) rollDigits(v, before[k]);
    });
  }

  // --- 01 Where ---------------------------------------------------------------------------
  function renderWhere(all) {
    const mapPool = pool({ city: true });
    const perCity = new Map();
    for (const i of mapPool) {
      const c = D.jobs[i][J.CITY];
      if (c >= 0) perCity.set(c, (perCity.get(c) || 0) + 1);
    }
    const ranked = [...perCity].sort((a, b) => b[1] - a[1]);
    const labelled = new Set(ranked.slice(0, 6).map(([c]) => c));
    if (state.city >= 0) labelled.add(state.city);
    bubbleMap(
      document.getElementById("map"),
      D.cities.map((c, i) => ({
        key: i,
        name: c.name,
        lat: c.lat,
        lon: c.lon,
        value: perCity.get(i) || 0,
        selected: state.city === i,
        label: labelled.has(i),
        tip: `<strong>${esc(c.name)}</strong><br>${fmt.int(perCity.get(i) || 0)} jobs`,
      })),
    );

    const fieldPool = pool({ field: true });
    const perCat = new Map();
    for (const i of fieldPool) perCat.set(D.jobs[i][J.CAT], (perCat.get(D.jobs[i][J.CAT]) || 0) + 1);
    const rows = [...perCat]
      .sort((a, b) => b[1] - a[1])
      .map(([k, n]) => ({
        key: k,
        label: catLabel(k),
        value: n,
        text: fmt.int(n),
        selected: state.field === k,
        tip: `<strong>${esc(catLabel(k))}</strong><br>${fmt.int(n)} jobs · ${fmt.pct(n / fieldPool.length, 0)}`,
      }));
    barList(document.getElementById("fields"), rows);

    const topCity = ranked[0];
    const topField = rows[0];
    const el = document.getElementById("where-insight");
    if (!all.length || !topCity) el.innerHTML = "No jobs match these filters.";
    else if (state.city >= 0) {
      el.innerHTML = `<strong>${fmt.int(all.length)}</strong> jobs in ${esc(D.cities[state.city].name)}${state.field >= 0 ? ` in ${esc(catLabel(state.field))}` : ""}.${
        state.field < 0 && topField ? ` Most are in <strong>${esc(topField.label)}</strong>.` : ""}`;
    } else {
      const next = ranked.slice(1, 3).map(([c]) => esc(D.cities[c].name)).join(" and ");
      el.innerHTML = `<strong>${esc(D.cities[topCity[0]].name)}</strong> has the most jobs (${fmt.int(topCity[1])})${next ? `, followed by ${next}` : ""}.${
        state.field < 0 && topField ? ` The biggest field is <strong>${esc(topField.label)}</strong>.` : ""}`;
    }
  }

  // --- 02 Pay ---------------------------------------------------------------------------------
  function rangeRows(idxByKey, label, perCity) {
    return [...idxByKey]
      .map(([k, idx]) => [k, payStats(idx, perCity), idx.length])
      .filter(([, ps]) => ps.enough)
      .map(([k, ps, jobs]) => {
        const muted = ps.topShare > D.max_employer_share;
        return {
          key: k,
          label: label(k),
          p25: ps.p25,
          median: ps.median,
          p75: ps.p75,
          muted,
          selected: (state.payBy === "field" ? state.field : state.city) === k,
          tip: `<strong>${esc(label(k))}</strong><br>Median ${fmt.eur(ps.median)}/h<br>Half earn ${fmt.eur(ps.p25)}–${fmt.eur(ps.p75)}<br>${ps.n} roles from ${ps.employers} employers${muted ? `<br>${fmt.pct(ps.topShare, 0)} of these rates come from one employer` : ""}`,
          jobs,
        };
      })
      .sort((a, b) => b.median - a.median);
  }

  function renderPay(all = pool()) {
    const ps = payStats(all);
    const counts = new Array(PAY_BINS).fill(0);
    for (const v of ps.values) counts[Math.min(PAY_BINS - 1, Math.max(0, Math.floor(v) - PAY_MIN))]++;
    const bins = counts.map((n, b) => {
      const lo = PAY_MIN + b;
      return {
        label: b === PAY_BINS - 1 ? `${lo}+` : String(lo),
        value: n,
        inRange: ps.n > 0 && lo + 1 > ps.p25 && lo <= ps.p75,
        tip: `<strong>${b === PAY_BINS - 1 ? `€${lo} or more` : `€${lo}–${lo}.99`}</strong><br>${n} roles`,
      };
    });
    const hist = document.getElementById("pay-hist");
    if (ps.n) {
      histogram(hist, bins, {
        median: { pos: Math.min(PAY_BINS, Math.max(0, ps.median - PAY_MIN)), label: `median ${fmt.eur(ps.median)}` },
        axisTitle: `€ per hour · ${fmt.int(ps.n)} roles with a stated rate`,
      });
      hist.insertAdjacentHTML("beforeend", `<div class="pay-trio">
        <div><span>${fmt.eur(ps.p25)}</span>a quarter earn less</div>
        <div class="mid"><span>${fmt.eur(ps.median)}</span>median</div>
        <div><span>${fmt.eur(ps.p75)}</span>a quarter earn more</div></div>`);
    } else hist.innerHTML = `<p class="empty">No stated rates for this selection.</p>`;

    // Rows: fields (ignoring the field filter) or cities (ignoring the city filter).
    const groups = new Map();
    const src = state.payBy === "field" ? pool({ field: true }) : pool({ city: true });
    const col = state.payBy === "field" ? J.CAT : J.CITY;
    for (const i of src) {
      const k = D.jobs[i][col];
      if (k < 0) continue;
      if (!groups.has(k)) groups.set(k, []);
      groups.get(k).push(i);
    }
    let rows = rangeRows(groups, state.payBy === "field" ? catLabel : (k) => D.cities[k].name, state.payBy === "city");
    if (state.payBy === "city") rows = rows.sort((a, b) => b.jobs - a.jobs).slice(0, 12).sort((a, b) => b.median - a.median);
    // Scale to the data (a dot plot needs no zero line): the differences are a few euros.
    const lo = Math.floor(Math.min(...rows.map((r) => r.p25), 15)) - 0.5;
    const hi = Math.ceil(Math.max(...rows.map((r) => r.p75), 17)) + 0.5;
    const ticks = [];
    for (let t = Math.ceil(lo); t <= hi; t += hi - lo > 9 ? 2 : 1) ticks.push(t);
    dotRange(document.getElementById("pay-range"), rows, { min: lo, max: hi, ticks });
    document.querySelectorAll("#pay-seg button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.by === state.payBy)));

    const el = document.getElementById("pay-insight");
    if (!ps.enough) {
      el.innerHTML = `Too few jobs state an hourly rate for this selection (${ps.n}). Try widening the filters.`;
      return;
    }
    const best = rows.find((r) => !r.muted);
    const free = state.payBy === "field" ? state.field < 0 : state.city < 0;
    el.innerHTML = `Half of the jobs pay between <strong>${fmt.eur(ps.p25)}</strong> and <strong>${fmt.eur(ps.p75)}</strong> an hour.${
      best && free ? ` <strong>${esc(best.label)}</strong> pays the most (${fmt.eur(best.median)}).` : ""}`;
  }

  // --- 03 Skills --------------------------------------------------------------------------
  function topSkills(idx) {
    const counts = new Array(D.skills.length).fill(0);
    for (const i of idx) for (const s of D.jobs[i][J.SKILLS]) counts[s]++;
    return counts
      .map((n, s) => ({ key: s, id: D.skills[s].id, label: D.skills[s].label, group: D.skills[s].group, n, share: idx.length ? n / idx.length : 0 }))
      .filter((x) => x.n > 0)
      .sort((a, b) => b.n - a.n);
  }

  function renderSkills(all = pool()) {
    const ranked = topSkills(all);
    const groups = ["All", ...new Set(ranked.map((r) => r.group))];
    if (!groups.includes(state.skillGroup)) state.skillGroup = "All";
    document.getElementById("skill-groups").innerHTML = groups
      .slice(0, 10)
      .map((g) => `<button type="button" class="chip" data-group="${esc(g)}" aria-pressed="${state.skillGroup === g}">${esc(g)}</button>`)
      .join("");
    const shown = ranked.filter((r) => state.skillGroup === "All" || r.group === state.skillGroup).slice(0, 15);
    if (state.skill == null || !shown.some((r) => r.key === state.skill)) state.skill = shown[0]?.key ?? null;
    barList(
      document.getElementById("skill-bars"),
      shown.map((r) => ({
        key: r.key,
        label: r.label,
        value: r.share,
        text: fmt.pct(r.share, r.share < 0.1 ? 1 : 0),
        selected: r.key === state.skill,
        tip: `<strong>${esc(r.label)}</strong><br>${fmt.int(r.n)} of ${fmt.int(all.length)} jobs`,
      })),
      { empty: "No skills found for this selection.", dim: false },
    );

    const prog = ranked.find((r) => r.group === "Programming");
    const top = ranked[0];
    document.getElementById("skills-insight").innerHTML = top
      ? `<strong>${esc(top.label)}</strong> is asked for in ${fmt.pct(top.share, 0)} of jobs.${
          prog ? ` The most wanted programming language is <strong>${esc(prog.label)}</strong> (${fmt.pct(prog.share, 1)}).` : ""}`
      : "";
    renderSkillDetail(all, ranked);
  }

  function renderSkillDetail(all, ranked) {
    const el = document.getElementById("skill-detail");
    const r = ranked.find((x) => x.key === state.skill);
    if (!r) {
      el.innerHTML = `<p class="empty">Pick a skill to see details.</p>`;
      return;
    }
    const withIt = all.filter((i) => D.jobs[i][J.SKILLS].includes(r.key));
    const ps = payStats(withIt);
    const overall = payStats(all);
    const cats = new Map();
    for (const i of withIt) cats.set(D.jobs[i][J.CAT], (cats.get(D.jobs[i][J.CAT]) || 0) + 1);
    const topCats = [...cats].sort((a, b) => b[1] - a[1]).slice(0, 4);
    const have = ctx.match.has(r.key);
    let diff = ps.enough && overall.enough ? ps.median / overall.median - 1 : null;
    if (diff != null && Math.abs(diff) < 0.005) diff = null;
    el.innerHTML = `
      <div class="sd-name">${esc(r.label)}</div>
      <p class="sd-big">in ${fmt.pct(r.share, 1)} of jobs · ${fmt.int(r.n)} postings</p>
      <div class="sd-stats">
        <div class="sd-stat"><div class="v">${ps.enough ? fmt.eur(ps.median) : "—"}</div><div class="l">median pay${diff != null ? ` (${fmt.signedPct(diff)} vs all)` : ""}</div></div>
        <div class="sd-stat"><div class="v">${fmt.pct(topCats[0] ? topCats[0][1] / withIt.length : null, 0)}</div><div class="l">in ${esc(topCats[0] ? catLabel(topCats[0][0]) : "—")}</div></div>
      </div>
      <h3>Where it's asked for</h3>
      <div id="sd-fields"></div>
      <div class="sd-actions">
        <button type="button" class="btn" data-act="jobs">Show ${fmt.int(r.n)} jobs</button>
        <button type="button" class="chip" data-act="have" aria-pressed="${have}">${have ? "✓ In your skills" : "+ I have this"}</button>
      </div>`;
    barList(
      el.querySelector("#sd-fields"),
      topCats.map(([k, n]) => ({ label: catLabel(k), value: n / withIt.length, text: fmt.pct(n / withIt.length, 0) })),
      { max: 1 },
    );
    el.querySelector('[data-act="jobs"]').addEventListener("click", () => ctx.match.showSkill(r.key));
    el.querySelector('[data-act="have"]').addEventListener("click", () => ctx.match.toggleSkill(r.key));
  }

  // --- 05 Programmes (whole market, not filtered) ------------------------------------------------
  function renderMajors() {
    const majors = [...S.majors].sort((a, b) => MAJOR_ORDER.indexOf(a.id) - MAJOR_ORDER.indexOf(b.id));
    const tabs = document.getElementById("mj-tabs");
    const panel = document.getElementById("mj-panel");
    let current = majors.find((m) => m.id === params.get("programme"))?.id ?? majors[0].id;
    tabs.innerHTML = majors.map((m) => `<button type="button" class="tab" role="tab" data-id="${m.id}">${esc(m.label)}</button>`).join("");
    tabs.addEventListener("click", (e) => {
      const b = e.target.closest(".tab");
      if (b) { current = b.dataset.id; draw(); }
    });
    panel.addEventListener("click", (e) => {
      const s = e.target.closest("[data-skill]");
      if (!s) return;
      const idx = D.skills.findIndex((x) => x.id === s.dataset.skill);
      if (idx >= 0) ctx.match.toggleSkill(idx);
    });
    const draw = () => {
      tabs.querySelectorAll(".tab").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.id === current)));
      const m = majors.find((x) => x.id === current);
      const topField = m.categories[0];
      panel.innerHTML = `
        <div class="mj-stats">
          <div class="mj-stat"><div class="label">Jobs mentioning it</div><div class="value">${fmt.int(m.jobs)}</div></div>
          <div class="mj-stat"><div class="label">Share of all jobs</div><div class="value">${fmt.pct(m.share, 0)}</div></div>
          <div class="mj-stat"><div class="label">Median pay</div><div class="value">${fmt.eur(m.median_pay)}</div></div>
          <div class="mj-stat"><div class="label">Top field</div><div class="value" style="font-size:20px">${esc(topField ? catLabel(D.categories.indexOf(topField.key)) : "—")}</div></div>
        </div>
        <div class="mj-grid">
          <div><h3>Fields</h3><div id="mj-fields"></div></div>
          <div>
            <h3>Skills they ask for <span class="hint-inline">click to add to yours</span></h3>
            <div class="chips-row">${m.skills
              .filter((x) => D.skills.some((s) => s.id === x.key))
              .map((x) => {
                const idx = D.skills.findIndex((s) => s.id === x.key);
                return `<button type="button" class="chip" data-skill="${esc(x.key)}" aria-pressed="${ctx.match.has(idx)}">${esc(skillLabel(x.key))}</button>`;
              })
              .join("")}</div>
            <h3 style="margin-top:18px">Newest postings</h3>
            <div class="job-list">${m.examples.slice(0, 5).map((j) => `<div class="job"><a href="${esc(j.url)}" target="_blank" rel="noopener">${esc(j.title)}</a><div class="meta">${esc(j.company)} · ${esc(j.city || "—")}</div><div class="side">${j.pay != null ? `<span class="pay">${fmt.eur(j.pay)}</span>` : ""}</div></div>`).join("")}</div>
          </div>
        </div>`;
      barList(
        panel.querySelector("#mj-fields"),
        m.categories.map((c) => ({ label: catLabel(D.categories.indexOf(c.key)), value: c.jobs, text: fmt.int(c.jobs) })),
      );
    };
    ctx.showProgramme = (id) => {
      if (!majors.some((m) => m.id === id)) return;
      current = id;
      draw();
    };
    ctx.redrawProgramme = draw;
    draw();
  }

  // --- 06 Trends (whole market) ----------------------------------------------------------------------
  function renderTrends() {
    const days = H.dates.length;
    document.getElementById("trends-insight").textContent =
      days < 7
        ? `A snapshot is taken every morning since ${fmt.date(H.dates[0])}. Trends appear after a few weeks.`
        : `${days} daily snapshots since ${fmt.date(H.dates[0])}.`;
    lineChart(document.getElementById("tr-jobs"), H.dates, H.series["total:all:jobs"], { label: "Postings", format: fmt.int });
    lineChart(document.getElementById("tr-pay"), H.dates, H.series["total:all:median_pay"], { label: "Median pay", format: fmt.eur });
  }

  // --- Wiring -----------------------------------------------------------------------------------------
  function syncUrl() {
    const p = new URLSearchParams();
    if (state.field >= 0) p.set("field", D.categories[state.field]);
    if (state.city >= 0) p.set("city", D.cities[state.city].name);
    if (state.noGerman) p.set("german", "no");
    const skills = ctx.match.ids();
    if (skills.length) p.set("skills", skills.join(","));
    const url = new URL(location.href);
    url.search = p.toString();
    history.replaceState(null, "", url);
  }

  function render() {
    const all = pool();
    renderFilters(all);
    renderWhere(all);
    renderPay(all);
    renderSkills(all);
    ctx.match.update();
    renderTiles(all);
    syncUrl();
  }
  // Called by the match section when "your skills" change.
  ctx.onSkillsChanged = () => {
    renderTiles(pool());
    renderSkills();
    ctx.redrawProgramme?.();
    syncUrl();
  };

  ctx.match = initMatch(ctx, (params.get("skills") || "").split(",").filter(Boolean));
  initCv(ctx);
  renderMajors();
  renderTrends();
  render();

  const ageDays = Math.floor((Date.now() - new Date(`${D.as_of}T12:00:00`)) / 864e5);
  if (ageDays > 2) {
    const stale = document.getElementById("stale");
    stale.textContent = `The daily update hasn't run for ${ageDays} days, so these numbers may be out of date.`;
    stale.hidden = false;
  }
  const src = S.totals.by_source || {};
  document.querySelector(".lede").textContent =
    `Every Werkstudent posting on the Bundesagentur für Arbeit job board${src.arbeitnow ? `, plus ${fmt.int(src.arbeitnow)} from company career sites` : ""}.`;
  const scanned = S.generated_at
    ? new Date(S.generated_at).toLocaleString("en-GB", { timeZone: "Europe/Berlin", day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).replace(",", "")
    : fmt.date(D.as_of);
  const status = document.getElementById("status");
  status.classList.toggle("is-stale", ageDays > 2);
  status.innerHTML = `<span class="status-dot" aria-hidden="true">●</span> ${ageDays > 2 ? "STALE" : "LIVE"} · LAST SCAN <time datetime="${esc(S.generated_at || D.as_of)}">${esc(scanned)}</time>`;

  // Sections get their height only now, so jump to #anchor again.
  const target = location.hash && document.getElementById(location.hash.slice(1));
  if (target) target.scrollIntoView({ behavior: "instant" });
}

main();
