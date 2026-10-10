import { barList, bubbleMap, dotRange, esc, fmt, histogram, initTooltip, lineChart, rollDigits, survivalChart } from "./charts.js?v=dev";
import { initCv } from "./cv.js?v=dev";
import { applyStatic, fieldLabel, groupLabel, initLangSwitch, lang, skillLabel as localSkillLabel, t } from "./i18n.js?v=dev";
import { initMatch } from "./match.js?v=dev";
import { initSql } from "./sql.js?v=dev";
import { medianCI } from "./stats.js?v=dev";

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
  applyStatic();
  initLangSwitch();
  initTooltip();
  let S, D, H, L, C;
  try {
    // lifetimes and cooccurrence are extras: the page works without them.
    [S, D, H, L, C] = await Promise.all([
      load("summary"), load("checker"), load("history"),
      load("lifetimes").catch(() => null), load("cooccurrence").catch(() => null),
    ]);
  } catch (e) {
    document.getElementById("tiles").innerHTML = `<p class="stale">${esc(t("load.error", { msg: e.message }))}</p>`;
    return;
  }

  // Labels in the page's language (the data has English ones).
  for (const s of [...D.skills, ...S.skills]) s.label = localSkillLabel(s.id, s.label);
  for (const k of Object.keys(D.category_labels)) D.category_labels[k] = fieldLabel(k, D.category_labels[k]);

  const params = new URLSearchParams(location.search);
  const state = {
    field: Math.max(-1, D.categories.indexOf(params.get("field"))),
    city: Math.max(-1, D.cities.findIndex((c) => c.name === params.get("city"))),
    noGerman: params.get("german") === "no",
    payBy: "field",
    skillGroup: "All",
    skill: null,
  };

  const catLabel = (i) => (i < 0 ? fieldLabel("other", "Other") : D.category_labels[D.categories[i]] ?? D.categories[i]);
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
    const median = quantile(values, 0.5);
    // A median needs enough roles and employers, and a 95% CI no wider than a quarter of it.
    const sample = values.length >= D.min_pay_sample && byCompany.size >= 5;
    const ci = sample ? medianCI(values) : null;
    const precise = Boolean(ci) && (ci[1] - ci[0]) / median <= (D.max_ci_rel_width ?? 0.25);
    return {
      n: values.length,
      values,
      p25: quantile(values, 0.25),
      median,
      p75: quantile(values, 0.75),
      ci,
      employers: byCompany.size,
      topShare: values.length ? top / values.length : 0,
      enough: sample && precise,
      why: !sample ? t("why.few") : precise ? "" : t("why.unsure"),
    };
  }
  // "95% CI €15.40–17.60" / "95%-KI 15,40–17,60 €"
  const ciText = (lo, hi) => (lo == null ? "" : t("ci", { lo: fmt.num2(lo), hi: fmt.num2(hi) }));

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

  // Phones: the filters live in a bottom sheet; active ones show as removable chips.
  const sheet = document.getElementById("f-sheet");
  const fOpen = document.getElementById("f-open");
  const backdrop = document.getElementById("f-backdrop");
  function setSheet(open) {
    sheet.classList.toggle("open", open);
    backdrop.hidden = !open;
    fOpen.setAttribute("aria-expanded", String(open));
    document.body.classList.toggle("sheet-open", open);
    (open ? fField : fOpen).focus({ preventScroll: true });
  }
  fOpen.addEventListener("click", () => setSheet(true));
  for (const id of ["f-backdrop", "f-close", "f-done"]) document.getElementById(id).addEventListener("click", () => setSheet(false));
  document.addEventListener("keydown", (e) => e.key === "Escape" && sheet.classList.contains("open") && setSheet(false));
  document.getElementById("f-chips").addEventListener("click", (e) => {
    const b = e.target.closest("[data-clear]");
    if (!b) return;
    if (b.dataset.clear === "field") state.field = -1;
    if (b.dataset.clear === "city") state.city = -1;
    if (b.dataset.clear === "german") state.noGerman = false;
    render();
  });

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
    document.getElementById("f-count").textContent = t("filter.count", { n: fmt.int(all.length) });
    document.getElementById("f-done").textContent = t("filter.show", { n: fmt.int(all.length) });
    renderSubscribe();
    const chips = [
      state.field >= 0 && ["field", catLabel(state.field)],
      state.city >= 0 && ["city", D.cities[state.city].name],
      state.noGerman && ["german", t("filter.chip_no_german")],
    ].filter(Boolean);
    document.getElementById("f-chips").innerHTML = chips
      .map(([k, label]) => `<button type="button" class="filter-pill" data-clear="${k}" aria-label="${esc(t("filter.remove", { x: label }))}">${esc(label)} <span aria-hidden="true">✕</span></button>`)
      .join("");
  }

  // RSS feeds of new postings: all fields, plus the selected field's own feed.
  function renderSubscribe() {
    const field = state.field >= 0 ? D.categories[state.field] : null;
    const list = [["all", t("subscribe.all")], ...(field ? [[field, t("subscribe.field", { field: catLabel(state.field) })]] : [])];
    document.getElementById("subscribe").innerHTML = `
      <p>${esc(t("subscribe.text"))}</p>
      ${list.map(([id, label]) => `<div class="feed-row"><a href="feeds/${id}.xml">${esc(label)}</a>
        <button type="button" class="link-btn" data-copy="feeds/${id}.xml">${esc(t("subscribe.copy"))}</button></div>`).join("")}
      ${field ? "" : `<p class="hint">${esc(t("subscribe.hint"))}</p>`}`;
  }
  document.getElementById("subscribe").addEventListener("click", async (e) => {
    const b = e.target.closest("[data-copy]");
    if (!b) return;
    const url = new URL(b.dataset.copy, location.href).href;
    try {
      await navigator.clipboard.writeText(url);
      b.textContent = t("subscribe.copied");
    } catch {
      b.textContent = url; // no clipboard access: show the address to copy by hand
    }
    setTimeout(() => { b.textContent = t("subscribe.copy"); }, 2500);
  });

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
      { href: "#where", label: where ? t("tile.jobs_where", { where }) : t("tile.jobs_online"), value: fmt.int(all.length), sub: t("tile.places", { n: places, v: fmt.int(places) }) },
      { href: "#pay", label: t("tile.median"), value: ps.enough ? fmt.eur(ps.median) : "—", sub: ps.enough ? t("tile.per_hour", { ci: ciText(...ps.ci) }) : ps.why },
      { href: "#skills", label: t("tile.top_skill"), value: top ? top.label : "—", sub: top ? t("tile.skill_share", { pct: fmt.pct(top.share, 0) }) : "", small: true },
      { href: "#where", label: t("tile.most_jobs"), value: bigCity >= 0 ? D.cities[bigCity].name : "—", sub: bigCity >= 0 ? t("jobs.n", { n: bigCount, v: fmt.int(bigCount) }) : "", small: true },
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
        tip: `<strong>${esc(c.name)}</strong><br>${t("jobs.n", { n: perCity.get(i) || 0, v: fmt.int(perCity.get(i) || 0) })}`,
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
        tip: `<strong>${esc(catLabel(k))}</strong><br>${t("where.field_tip", { n: fmt.int(n), pct: fmt.pct(n / fieldPool.length, 0) })}`,
      }));
    barList(document.getElementById("fields"), rows);

    const topCity = ranked[0];
    const topField = rows[0];
    const el = document.getElementById("where-insight");
    if (!all.length || !topCity) el.textContent = t("where.none");
    else if (state.city >= 0) {
      el.innerHTML = t("where.city", { n: fmt.int(all.length), city: esc(D.cities[state.city].name), field: state.field >= 0 ? esc(catLabel(state.field)) : "" }) +
        (state.field < 0 && topField ? t("where.city_most", { field: esc(topField.label) }) : "");
    } else {
      const next = ranked.slice(1, 3).map(([c]) => esc(D.cities[c].name)).join(t("and"));
      el.innerHTML = t("where.top", { city: esc(D.cities[topCity[0]].name), n: fmt.int(topCity[1]), next }) +
        (state.field < 0 && topField ? t("where.biggest", { field: esc(topField.label) }) : "");
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
          tip: t("pay.range_tip", { label: esc(label(k)), median: fmt.eur(ps.median), ci: ciText(...ps.ci), p25: fmt.eur(ps.p25), p75: fmt.eur(ps.p75), n: fmt.int(ps.n), emp: fmt.int(ps.employers) }) +
            (muted ? t("pay.one_employer", { pct: fmt.pct(ps.topShare, 0) }) : ""),
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
        tip: `<strong>${t(b === PAY_BINS - 1 ? "pay.bin_top" : "pay.bin", { lo })}</strong><br>${t("pay.roles", { n, v: fmt.int(n) })}`,
      };
    });
    const hist = document.getElementById("pay-hist");
    if (ps.n) {
      histogram(hist, bins, {
        median: { pos: Math.min(PAY_BINS, Math.max(0, ps.median - PAY_MIN)), label: t("pay.median_marker", { v: fmt.eur(ps.median) }) },
        axisTitle: t("pay.axis", { n: fmt.int(ps.n) }),
      });
      hist.insertAdjacentHTML("beforeend", `<div class="pay-trio">
        <div><span>${fmt.eur(ps.p25)}</span>${t("pay.q1")}</div>
        <div class="mid"><span>${fmt.eur(ps.median)}</span>${t("pay.median")}${ps.ci ? `<small class="ci">${ciText(...ps.ci)}</small>` : ""}</div>
        <div><span>${fmt.eur(ps.p75)}</span>${t("pay.q3")}</div></div>`);
    } else hist.innerHTML = `<p class="empty">${esc(t("pay.no_rates"))}</p>`;

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
      el.textContent = t("pay.too_few", { n: fmt.int(ps.n) });
      return;
    }
    const best = rows.find((r) => !r.muted);
    const free = state.payBy === "field" ? state.field < 0 : state.city < 0;
    el.innerHTML = t("pay.insight", { p25: fmt.eur(ps.p25), p75: fmt.eur(ps.p75) }) +
      (best && free ? t("pay.best", { label: esc(best.label), v: fmt.eur(best.median) }) : "");
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
      .map((g) => `<button type="button" class="chip" data-group="${esc(g)}" aria-pressed="${state.skillGroup === g}">${esc(g === "All" ? t("skills.all") : groupLabel(g))}</button>`)
      .join("");
    const shown = ranked.filter((r) => state.skillGroup === "All" || r.group === state.skillGroup).slice(0, 15);
    if (state.skill == null || !ranked.some((r) => r.key === state.skill)) state.skill = shown[0]?.key ?? null;
    barList(
      document.getElementById("skill-bars"),
      shown.map((r) => ({
        key: r.key,
        label: r.label,
        value: r.share,
        text: fmt.pct(r.share, r.share < 0.1 ? 1 : 0),
        selected: r.key === state.skill,
        tip: `<strong>${esc(r.label)}</strong><br>${t("skills.bar_tip", { n: fmt.int(r.n), total: fmt.int(all.length) })}`,
      })),
      { empty: t("skills.empty"), dim: false },
    );

    const prog = ranked.find((r) => r.group === "Programming");
    const top = ranked[0];
    document.getElementById("skills-insight").innerHTML = top
      ? t("skills.insight", { skill: esc(top.label), pct: fmt.pct(top.share, 0) }) +
        (prog ? t("skills.prog", { skill: esc(prog.label), pct: fmt.pct(prog.share, 1) }) : "")
      : "";
    renderSkillDetail(all, ranked);
  }

  // Skills most often asked for together with this one (cooccurrence.json, whole market).
  function related(i) {
    const list = C?.skills?.[D.skills[i].id] ?? [];
    const chips = list
      .map(([id, lift, share]) => [D.skills.findIndex((s) => s.id === id), lift, share])
      .filter(([j]) => j >= 0)
      .map(([j, lift, share]) => `<button type="button" class="chip" data-skill="${j}"
          data-tip="${esc(`<strong>${esc(D.skills[j].label)}</strong><br>${t("skills.related_tip", { pct: fmt.pct(share, 0), skill: esc(D.skills[i].label), lift: lift.toLocaleString(lang === "de" ? "de-DE" : "en-GB") })}`)}">${esc(D.skills[j].label)} <span class="lift">${lift.toLocaleString(lang === "de" ? "de-DE" : "en-GB")}×</span></button>`)
      .join("");
    return chips ? `<h3>${esc(t("skills.related"))}</h3><div class="chips-row related">${chips}</div>` : "";
  }

  function renderSkillDetail(all, ranked) {
    const el = document.getElementById("skill-detail");
    const r = ranked.find((x) => x.key === state.skill);
    if (!r) {
      el.innerHTML = `<p class="empty">${esc(t("skills.pick"))}</p>`;
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
      <p class="sd-big">${t("skills.share", { pct: fmt.pct(r.share, 1), n: fmt.int(r.n) })}</p>
      <div class="sd-stats">
        <div class="sd-stat"><div class="v">${ps.enough ? fmt.eur(ps.median) : "—"}</div><div class="l">${t("skills.median_pay")}${diff != null ? t("skills.vs_all", { d: fmt.signedPct(diff) }) : ""}</div>${
          ps.enough ? `<div class="ci">${ciText(...ps.ci)}</div>` : `<div class="ci">${ps.why}</div>`}</div>
        <div class="sd-stat"><div class="v">${fmt.pct(topCats[0] ? topCats[0][1] / withIt.length : null, 0)}</div><div class="l">${esc(t("skills.in_field", { field: topCats[0] ? catLabel(topCats[0][0]) : "—" }))}</div></div>
      </div>
      <h3>${esc(t("skills.where"))}</h3>
      <div id="sd-fields"></div>
      ${related(r.key)}
      <div class="sd-actions">
        <button type="button" class="btn" data-act="jobs">${t("skills.show_jobs", { n: fmt.int(r.n) })}</button>
        <button type="button" class="chip" data-act="have" aria-pressed="${have}">${t(have ? "skills.have" : "skills.add")}</button>
      </div>`;
    barList(
      el.querySelector("#sd-fields"),
      topCats.map(([k, n]) => ({ label: catLabel(k), value: n / withIt.length, text: fmt.pct(n / withIt.length, 0) })),
      { max: 1 },
    );
    el.querySelector('[data-act="jobs"]').addEventListener("click", () => ctx.match.showSkill(r.key));
    el.querySelector(".related")?.addEventListener("click", (e) => {
      const b = e.target.closest("[data-skill]");
      if (!b) return;
      state.skill = Number(b.dataset.skill);
      renderSkills();
    });
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
          <div class="mj-stat"><div class="label">${t("programmes.jobs")}</div><div class="value">${fmt.int(m.jobs)}</div></div>
          <div class="mj-stat"><div class="label">${t("programmes.share")}</div><div class="value">${fmt.pct(m.share, 0)}</div></div>
          <div class="mj-stat"><div class="label">${t("programmes.median")}</div><div class="value">${fmt.eur(m.median_pay)}</div>${
            m.median_pay != null ? `<div class="ci">${ciText(m.median_pay_lo, m.median_pay_hi)}</div>` : ""}</div>
          <div class="mj-stat"><div class="label">${t("programmes.top_field")}</div><div class="value" style="font-size:20px">${esc(topField ? catLabel(D.categories.indexOf(topField.key)) : "—")}</div></div>
        </div>
        <div class="mj-grid">
          <div><h3>${t("programmes.fields")}</h3><div id="mj-fields"></div></div>
          <div>
            <h3>${t("programmes.skills")} <span class="hint-inline">${t("programmes.skills_hint")}</span></h3>
            <div class="chips-row">${m.skills
              .filter((x) => D.skills.some((s) => s.id === x.key))
              .map((x) => {
                const idx = D.skills.findIndex((s) => s.id === x.key);
                return `<button type="button" class="chip" data-skill="${esc(x.key)}" aria-pressed="${ctx.match.has(idx)}">${esc(skillLabel(x.key))}</button>`;
              })
              .join("")}</div>
            <h3 style="margin-top:18px">${t("programmes.newest")}</h3>
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
        ? t("trends.early", { date: fmt.date(H.dates[0]) })
        : t("trends.days", { n: fmt.int(days), date: fmt.date(H.dates[0]) });
    lineChart(document.getElementById("tr-jobs"), H.dates, H.series["total:all:jobs"], { label: t("trends.postings"), format: fmt.int });
    lineChart(document.getElementById("tr-pay"), H.dates, H.series["total:all:median_pay"], {
      label: t("trends.median"), format: fmt.eur,
      band: { lo: H.series["total:all:median_pay_lo"], hi: H.series["total:all:median_pay_hi"] },
    });
    renderLifetimes();
  }

  // How long postings stay online: Kaplan–Meier curve from lifetimes.json.
  function renderLifetimes() {
    const card = document.getElementById("lifetimes");
    if (!L) {
      card.hidden = true;
      return;
    }
    survivalChart(document.getElementById("tr-life"), L.curve.rows);
    const fields = Object.entries(L.by_field)
      .filter(([, f]) => f.median_days != null)
      .sort((a, b) => a[1].median_days - b[1].median_days);
    const median = L.median_days != null ? t("life.median", { n: L.median_days }) : t("life.no_median", { n: L.observed_until });
    document.getElementById("tr-life-note").innerHTML = median + t("life.based", { n: fmt.int(L.postings), gone: fmt.int(L.gone) }) +
      (fields.length ? t("life.shortest", { list: fields.slice(0, 3).map(([k, f]) => `${esc(catLabel(D.categories.indexOf(k)))} ${t("life.days", { n: f.median_days })}`).join(", ") }) : "");
  }

  // --- Wiring -----------------------------------------------------------------------------------------
  function syncUrl() {
    const p = new URLSearchParams();
    if (state.field >= 0) p.set("field", D.categories[state.field]);
    if (state.city >= 0) p.set("city", D.cities[state.city].name);
    if (state.noGerman) p.set("german", "no");
    if (lang !== "en") p.set("lang", lang);
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
  initSql();
  renderMajors();
  renderTrends();
  render();

  const ageDays = Math.floor((Date.now() - new Date(`${D.as_of}T12:00:00`)) / 864e5);
  if (ageDays > 2) {
    const stale = document.getElementById("stale");
    stale.textContent = t("status.stale_note", { n: ageDays });
    stale.hidden = false;
  }
  const src = S.totals.by_source || {};
  document.querySelector(".lede").textContent = t("hero.lede", { plus: src.arbeitnow ? fmt.int(src.arbeitnow) : "" });
  const scanned = S.generated_at
    ? new Date(S.generated_at).toLocaleString(lang === "de" ? "de-DE" : "en-GB", { timeZone: "Europe/Berlin", day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).replace(",", "")
    : fmt.date(D.as_of);
  const status = document.getElementById("status");
  status.classList.toggle("is-stale", ageDays > 2);
  status.innerHTML = `<span class="status-dot" aria-hidden="true">●</span> ${t(ageDays > 2 ? "status.stale" : "status.live")} · ${t("status.last_scan")} <time datetime="${esc(S.generated_at || D.as_of)}">${esc(scanned)}</time>`;

  // Mark the section in view in the nav (the bottom tab bar on phones).
  const navLinks = [...document.querySelectorAll(".nav a")];
  const spy = new IntersectionObserver(
    (entries) => {
      for (const e of entries) {
        if (!e.isIntersecting) continue;
        navLinks.forEach((a) => (a.hash === `#${e.target.id}` ? a.setAttribute("aria-current", "location") : a.removeAttribute("aria-current")));
      }
    },
    { rootMargin: "-40% 0px -55% 0px" },
  );
  navLinks.forEach((a) => spy.observe(document.querySelector(a.hash)));
  spy.observe(document.querySelector(".hero"));

  // Sections get their height only now, so jump to #anchor again.
  const target = location.hash && document.getElementById(location.hash.slice(1));
  if (target) target.scrollIntoView({ behavior: "instant" });
}

main();
