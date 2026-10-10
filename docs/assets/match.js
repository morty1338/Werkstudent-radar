// "Which jobs fit you?": your skills (picked by hand or found in your CV),
// how many postings you match, what to learn next, and the postings themselves.
//
// A posting is a match when you have nearly all the skills it lists: you may
// miss one in four (rounded down), so 1–3 listed skills need all of them,
// 4–7 allow one gap, 8+ allow two.

import { esc, fmt } from "./charts.js?v=dev";

const POPULAR = 24;
const PAGE = 15;

export function initMatch(ctx, initialIds) {
  const { D, J } = ctx;
  const idxById = new Map(D.skills.map((s, i) => [s.id, i]));
  const byDemand = D.skills.map((_, i) => i).sort((a, b) => D.skills[b].jobs - D.skills[a].jobs);
  const selected = new Set(initialIds.filter((id) => idxById.has(id)).map((id) => idxById.get(id)));
  const st = { tab: null, sort: "best", shown: PAGE, search: "", showAll: false, mustSkill: null, cvFound: new Set() };
  let postings = null;
  let loading = null;
  let last = null;

  const el = {
    chips: document.getElementById("my-chips"),
    search: document.getElementById("my-search"),
    all: document.getElementById("my-all"),
    clear: document.getElementById("my-clear"),
    summary: document.getElementById("match-summary"),
    tabs: document.getElementById("job-tabs"),
    sort: document.getElementById("job-sort"),
    list: document.getElementById("job-list"),
    more: document.getElementById("job-more"),
    chip: document.getElementById("job-filter-chip"),
  };

  // --- Events ---------------------------------------------------------------------------
  el.search.addEventListener("input", () => { st.search = el.search.value.trim().toLowerCase(); renderChips(); });
  el.all.addEventListener("click", () => { st.showAll = !st.showAll; renderChips(); });
  el.clear.addEventListener("click", () => { selected.clear(); st.cvFound.clear(); changed(); });
  el.chips.addEventListener("click", (e) => {
    const c = e.target.closest("[data-skill]");
    if (c) toggleSkill(Number(c.dataset.skill));
  });
  el.summary.addEventListener("click", (e) => {
    const c = e.target.closest("[data-skill]");
    if (c) toggleSkill(Number(c.dataset.skill));
  });
  el.tabs.addEventListener("click", (e) => {
    const t = e.target.closest("[data-tab]");
    if (!t) return;
    st.tab = t.dataset.tab;
    st.shown = PAGE;
    renderList();
  });
  el.sort.addEventListener("change", () => { st.sort = el.sort.value; renderList(); });
  el.more.addEventListener("click", () => { st.shown += PAGE; renderList(); });
  el.chip.addEventListener("click", (e) => {
    if (e.target.closest("button")) { st.mustSkill = null; renderList(); }
  });

  // Load the posting titles once the section comes into view.
  new IntersectionObserver((entries, obs) => {
    if (entries.some((e) => e.isIntersecting)) {
      ensurePostings();
      obs.disconnect();
    }
  }, { rootMargin: "600px" }).observe(document.getElementById("match"));

  function ensurePostings() {
    if (!loading) {
      loading = fetch("data/postings.json", { cache: "no-cache" })
        .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
        .then((data) => {
          // Both files come from the same build; otherwise positions don't line up.
          if (data.as_of !== D.as_of || data.rows.length !== D.jobs.length) throw new Error("the data is being updated, please reload");
          postings = data;
          renderList();
        })
        .catch((err) => { el.list.innerHTML = `<p class="empty">Couldn't load the postings (${esc(err.message)}).</p>`; });
    }
    return loading;
  }

  // --- State changes ----------------------------------------------------------------------------
  function toggleSkill(i) {
    if (selected.has(i)) selected.delete(i);
    else selected.add(i);
    changed();
  }

  function setSkills(idxs, { fromCv = false } = {}) {
    selected.clear();
    idxs.forEach((i) => selected.add(i));
    st.cvFound = fromCv ? new Set(idxs) : new Set();
    st.tab = "match";
    st.shown = PAGE;
    changed();
  }

  function showSkill(i) {
    st.mustSkill = i;
    st.tab = "all";
    st.shown = PAGE;
    update();
    document.getElementById("match").scrollIntoView({ behavior: "smooth" });
    ensurePostings();
  }

  function changed() {
    if (!selected.size && st.tab !== "all") st.tab = null;
    update();
    ctx.onSkillsChanged?.();
  }

  // --- Matching ------------------------------------------------------------------------------------
  function evaluate() {
    const pool = ctx.pool();
    const listed = pool.filter((i) => D.jobs[i][J.SKILLS].length);
    const matched = [];
    const near = [];
    const gains = new Map();
    for (const i of listed) {
      const req = D.jobs[i][J.SKILLS];
      const missing = req.filter((s) => !selected.has(s));
      const allowed = Math.floor(req.length / 4);
      if (missing.length <= allowed) matched.push(i);
      else if (missing.length === allowed + 1) {
        near.push([i, missing]);
        for (const s of missing) gains.set(s, (gains.get(s) || 0) + 1);
      }
    }
    const learn = [...gains].sort((a, b) => b[1] - a[1] || D.skills[b[0]].jobs - D.skills[a[0]].jobs).slice(0, 5);
    return { pool, listed, matched, near, learn };
  }

  // --- Rendering -------------------------------------------------------------------------------------
  function renderChips() {
    const q = st.search;
    const visible = byDemand.filter((i) => {
      if (selected.has(i)) return true;
      const s = D.skills[i];
      if (q) return s.label.toLowerCase().includes(q) || s.id.includes(q);
      return st.showAll || byDemand.indexOf(i) < POPULAR;
    });
    // Your skills first, then the most asked-for ones.
    visible.sort((a, b) => (selected.has(b) - selected.has(a)) || D.skills[b].jobs - D.skills[a].jobs);
    el.chips.innerHTML = visible.length
      ? visible
          .map((i) => `<button type="button" class="chip${st.cvFound.has(i) ? " found" : ""}" data-skill="${i}" aria-pressed="${selected.has(i)}"
              title="Asked for in ${fmt.int(D.skills[i].jobs)} postings">${esc(D.skills[i].label)}</button>`)
          .join("")
      : `<p class="empty">No skill matches “${esc(q)}”.</p>`;
    el.all.textContent = st.showAll ? "Show fewer skills" : `Show all ${D.skills.length} skills`;
    el.all.hidden = Boolean(q);
    el.clear.hidden = !selected.size;
  }

  function renderSummary(r) {
    if (!selected.size) {
      el.summary.innerHTML = `<p class="match-empty">Upload your CV or tick a few skills, and this shows the share of jobs you already qualify for and what to learn next.</p>`;
      return;
    }
    const share = r.listed.length ? r.matched.length / r.listed.length : 0;
    el.summary.innerHTML = `
      <div class="match-big">${fmt.pct(share, 0)}</div>
      <div class="match-text">You qualify for <strong>${fmt.int(r.matched.length)}</strong> of ${fmt.int(r.listed.length)} jobs that list skills${
        r.near.length ? `, and are one skill away from <strong>${fmt.int(r.near.length)}</strong> more` : ""}.</div>
      <div class="meter" aria-hidden="true"><div style="width:${share * 100}%"></div></div>
      ${r.learn.length ? `<div class="learn"><span class="learn-label">Learn next:</span>${r.learn
        .map(([s, n]) => `<button type="button" class="chip add" data-skill="${s}" title="Opens ${n} more jobs">${esc(D.skills[s].label)} <small>+${fmt.int(n)}</small></button>`)
        .join("")}</div>` : ""}`;
  }

  function renderTabs(r) {
    if (!st.tab) st.tab = selected.size ? "match" : "all";
    const tabs = [
      ["match", `You qualify (${fmt.int(r.matched.length)})`, selected.size > 0],
      ["near", `One skill away (${fmt.int(r.near.length)})`, selected.size > 0],
      ["all", `All jobs (${fmt.int(r.pool.length)})`, true],
    ].filter((t) => t[2]);
    if (!tabs.some((t) => t[0] === st.tab)) st.tab = "all";
    el.tabs.innerHTML = tabs
      .map(([k, label]) => `<button type="button" class="tab" role="tab" data-tab="${k}" aria-selected="${st.tab === k}">${label}</button>`)
      .join("");
  }

  function renderList() {
    if (!last) return;
    const r = last;
    renderTabs(r);
    el.chip.innerHTML = st.mustSkill != null
      ? `<span class="filter-chip">Jobs asking for ${esc(D.skills[st.mustSkill].label)} <button type="button" aria-label="Remove">×</button></span>`
      : "";
    if (!postings) {
      el.list.innerHTML = `<p class="empty">Loading jobs…</p>`;
      el.more.hidden = true;
      ensurePostings();
      return;
    }
    let items = st.tab === "match" ? r.matched.map((i) => [i, null]) : st.tab === "near" ? r.near : r.pool.map((i) => [i, null]);
    if (st.mustSkill != null) items = items.filter(([i]) => D.jobs[i][J.SKILLS].includes(st.mustSkill));
    const date = (i) => postings.rows[i][4] || "";
    // Best fit: postings that ask for more of your skills first (a job asking for
    // Python, SQL and Power BI says more about you than one asking for MS Office).
    const fit = (i) => D.jobs[i][J.SKILLS].reduce((n, s) => n + selected.has(s), 0);
    const byDate = (a, b) => date(b).localeCompare(date(a));
    const byPay = (a, b) => (D.jobs[b][J.PAY] ?? -1) - (D.jobs[a][J.PAY] ?? -1);
    const sort = st.sort === "best" && !selected.size ? "newest" : st.sort;
    items.sort(([a], [b]) =>
      sort === "pay" ? byPay(a, b) || byDate(a, b)
        : sort === "best" ? fit(b) - fit(a) || byPay(a, b) || byDate(a, b)
          : byDate(a, b),
    );
    el.list.innerHTML = items.length
      ? items.slice(0, st.shown).map(([i, missing]) => row(i, missing)).join("")
      : `<p class="empty">${st.tab === "match" ? "No matches yet. Add skills, or check “One skill away”." : "No jobs for this selection."}</p>`;
    el.more.hidden = items.length <= st.shown;
    el.more.textContent = `Show more (${fmt.int(items.length - st.shown)} left)`;
  }

  function row(i, missing) {
    const [refnr, title, company, city, published] = postings.rows[i];
    const j = D.jobs[i];
    const url = postings.url.replace("{refnr}", encodeURIComponent(refnr));
    const need = missing ? `<span class="badge need">+ ${missing.map((s) => esc(D.skills[s].label)).join(" or ")}</span>` : "";
    const en = j[J.DE] <= 1 ? `<span class="badge en">${j[J.DE] === 0 ? "No German needed" : "German a plus"}</span>` : "";
    const yours = j[J.SKILLS].filter((s) => selected.has(s)).slice(0, 4).map((s) => esc(D.skills[s].label));
    return `<div class="job">
      <a href="${esc(url)}" target="_blank" rel="noopener">${esc(title)}</a>
      <div class="meta">${esc(company)} · ${esc(city || "—")}${published ? ` · ${esc(fmt.shortDate(published))}` : ""}</div>
      ${yours.length ? `<div class="why">✓ ${yours.join(" · ")}</div>` : ""}
      <div class="side">${j[J.PAY] != null ? `<span class="pay">${fmt.eur(j[J.PAY])}/h</span>` : ""}${need}${en}</div>
    </div>`;
  }

  function update() {
    last = evaluate();
    renderChips();
    renderSummary(last);
    renderList();
  }

  return {
    update,
    toggleSkill,
    setSkills,
    showSkill,
    has: (i) => selected.has(i),
    ids: () => [...selected].map((i) => D.skills[i].id),
    headline: () => {
      if (!selected.size || !last) return null;
      const share = last.listed.length ? last.matched.length / last.listed.length : 0;
      return { value: fmt.pct(share, 0), sub: `${fmt.int(last.matched.length)} jobs fit your ${selected.size} skills →` };
    },
  };
}
