// "Check your skills": runs entirely in the browser on docs/data/checker.json.
//
// A posting counts as a match when you have nearly all the skills it lists:
// you may miss one in four (rounded down), so 1–3 listed skills need all of
// them, 4–7 allow one gap, 8+ allow two. Postings that list no specific
// skills are left out of the percentage.

import { esc, fmt } from "./charts.js";

const GROUP_ORDER = [
  "Office & Tools", "ERP & CRM", "Business & Finance", "Marketing & Sales", "Data & AI",
  "Programming", "Web & Mobile", "Cloud & DevOps", "IT & Security", "Design & Media",
  "Engineering", "Science & Lab",
];
const POPULAR_COUNT = 36;
const MIN_PAY_FOR_MEDIAN = 10;
const LIST_PAGE = 20;

export function initChecker(data, labels) {
  const { jobs, skills, categories, cities } = data;
  const data_as_of = data.as_of;
  const idxById = new Map(skills.map((s, i) => [s.id, i]));
  const popular = new Set(
    skills.map((s, i) => [s.jobs, i]).sort((a, b) => b[0] - a[0]).slice(0, POPULAR_COUNT).map(([, i]) => i),
  );

  const state = { selected: new Set(), field: -1, city: -2, noGerman: false, showAll: false, search: "" };

  const el = {
    chips: document.getElementById("ck-chips"),
    result: document.getElementById("ck-result"),
    search: document.getElementById("ck-search"),
    field: document.getElementById("ck-field"),
    city: document.getElementById("ck-city"),
    noGerman: document.getElementById("ck-nogerman"),
    all: document.getElementById("ck-all"),
    clear: document.getElementById("ck-clear"),
    share: document.getElementById("ck-share"),
    mini: document.getElementById("ck-mini"),
    list: document.getElementById("ck-list"),
    listBody: document.getElementById("ck-list-body"),
    listTabs: document.getElementById("ck-list-tabs"),
    listSort: document.getElementById("ck-list-sort"),
    listMore: document.getElementById("ck-list-more"),
  };
  let lastResult = null;

  categories.forEach((c, i) => el.field.add(new Option(labels.category(c), i)));
  cities.forEach((c, i) => el.city.add(new Option(c, i)));
  el.city.add(new Option("Other places", -1));

  // Restore a shared selection from ?skills=sql,python
  const fromUrl = new URLSearchParams(location.search).get("skills");
  if (fromUrl) {
    fromUrl.split(",").forEach((id) => idxById.has(id) && state.selected.add(idxById.get(id)));
  }

  el.search.addEventListener("input", () => {
    state.search = el.search.value.trim().toLowerCase();
    renderChips();
  });
  el.field.addEventListener("change", () => {
    state.field = el.field.value === "" ? -1 : Number(el.field.value);
    update();
  });
  el.city.addEventListener("change", () => {
    state.city = el.city.value === "" ? -2 : Number(el.city.value);
    update();
  });
  el.noGerman.addEventListener("change", () => {
    state.noGerman = el.noGerman.checked;
    update();
  });
  el.all.addEventListener("click", () => {
    state.showAll = !state.showAll;
    renderChips();
  });
  el.clear.addEventListener("click", () => {
    state.selected.clear();
    update();
  });
  el.share.addEventListener("click", async () => {
    const url = shareUrl();
    try {
      await navigator.clipboard.writeText(url);
      el.share.textContent = "Link copied";
    } catch {
      prompt("Copy this link:", url);
    }
    setTimeout(() => (el.share.textContent = "Copy link to my selection"), 2000);
  });
  el.chips.addEventListener("click", (e) => {
    const chip = e.target.closest(".chip");
    if (!chip) return;
    toggle(Number(chip.dataset.i));
  });
  el.result.addEventListener("click", (e) => {
    const s = e.target.closest(".suggestion");
    if (s) toggle(Number(s.dataset.i));
    const open = e.target.closest("[data-list]");
    if (open) openList(open.dataset.list);
  });
  el.listTabs.addEventListener("click", (e) => {
    const tab = e.target.closest("[data-tab]");
    if (!tab) return;
    listState.tab = tab.dataset.tab;
    listState.shown = LIST_PAGE;
    renderList();
  });
  el.listSort.addEventListener("change", () => {
    listState.sort = el.listSort.value;
    renderList();
  });
  el.listMore.addEventListener("click", () => {
    listState.shown += LIST_PAGE;
    renderList();
  });

  function toggle(i) {
    if (state.selected.has(i)) state.selected.delete(i);
    else state.selected.add(i);
    update();
  }

  function shareUrl() {
    const ids = [...state.selected].map((i) => skills[i].id).join(",");
    const url = new URL(location.href);
    url.search = ids ? `?skills=${ids}` : "";
    url.hash = "check";
    return url.toString();
  }

  function renderChips() {
    const q = state.search;
    const visible = (s, i) =>
      state.selected.has(i) || (q ? s.label.toLowerCase().includes(q) || s.id.includes(q) : state.showAll || popular.has(i));
    const groups = new Map(GROUP_ORDER.map((g) => [g, []]));
    skills.forEach((s, i) => {
      if (!visible(s, i)) return;
      if (!groups.has(s.group)) groups.set(s.group, []);
      groups.get(s.group).push(i);
    });
    const html = [...groups]
      .filter(([, list]) => list.length)
      .map(
        ([g, list]) => `<div class="chip-group"><h4>${esc(g)}</h4><div class="chips">${list
          .sort((a, b) => skills[b].jobs - skills[a].jobs)
          .map(
            (i) => `<button type="button" class="chip" data-i="${i}" aria-pressed="${state.selected.has(i)}"
              title="${esc(skills[i].label)}: in ${fmt.int(skills[i].jobs)} postings">${esc(skills[i].label)}</button>`,
          )
          .join("")}</div></div>`,
      )
      .join("");
    el.chips.innerHTML = html || `<p class="empty">No skill matches “${esc(q)}”.</p>`;
    el.all.textContent = state.showAll ? "Show popular skills only" : `Show all ${skills.length} skills`;
    el.all.hidden = Boolean(q);
  }

  // Works on job indices so the matching postings can be looked up in postings.json.
  function evaluate() {
    const pool = [];
    jobs.forEach(([cat, city, german], i) => {
      if (
        (state.field === -1 || cat === state.field) &&
        (state.city === -2 || city === state.city) &&
        (!state.noGerman || german <= 1)
      ) pool.push(i);
    });
    const listed = pool.filter((i) => jobs[i][4].length);
    const matched = [];
    const near = []; // [job index, missing skill indices]: one more skill and it's a match
    const pays = [];
    const gains = new Map();
    for (const i of listed) {
      const [, , , pay, req] = jobs[i];
      const missing = req.filter((s) => !state.selected.has(s));
      const allowed = Math.floor(req.length / 4);
      if (missing.length <= allowed) {
        matched.push(i);
        if (pay != null) pays.push(pay);
      } else if (missing.length === allowed + 1) {
        // Learning any one of these would turn the posting into a match.
        near.push([i, missing]);
        for (const s of missing) gains.set(s, (gains.get(s) || 0) + 1);
      }
    }
    const suggestions = [...gains].sort((a, b) => b[1] - a[1] || skills[b[0]].jobs - skills[a[0]].jobs).slice(0, 5);
    return { pool: pool.length, listed: listed.length, matches: matched.length, matched, near, pays, suggestions };
  }

  function median(values) {
    const v = [...values].sort((a, b) => a - b);
    const mid = v.length / 2;
    return v.length % 2 ? v[Math.floor(mid)] : (v[mid - 1] + v[mid]) / 2;
  }

  function renderResult() {
    const r = evaluate();
    lastResult = r;
    const share = r.listed ? r.matches / r.listed : 0;
    const scope = [
      state.field === -1 ? null : labels.category(categories[state.field]),
      state.city === -2 ? null : state.city === -1 ? "other places" : cities[state.city],
      state.noGerman ? "no German required" : null,
    ].filter(Boolean);

    const none = state.selected.size === 0;
    const pay =
      r.pays.length >= MIN_PAY_FOR_MEDIAN
        ? `<div class="result-block"><h4>Typical pay of your matches</h4><p>${fmt.eur(median(r.pays))}/h median <span class="hint">(${r.pays.length} matches state pay)</span></p></div>`
        : "";
    const sugg = r.suggestions.length
      ? `<div class="result-block"><h4>${none ? "Most useful skills to start with" : "Learn next"}</h4>${r.suggestions
          .map(
            ([i, n]) => `<button type="button" class="suggestion" data-i="${i}" title="Add ${esc(skills[i].label)}">
              <span>${esc(skills[i].label)}</span>
              <span class="gain">+${fmt.int(n)} · ${fmt.signedPct(n / r.listed)}</span>
            </button>`,
          )
          .join("")}<p class="small-print">Postings that would become a match, as count and percentage points.</p></div>`
      : "";

    // Compact summary that sticks to the bottom of the screen on phones,
    // where the full result sits below the long list of skills.
    el.mini.hidden = none;
    if (!none) {
      const next = r.suggestions[0];
      el.mini.innerHTML = `<span>You match <strong>${fmt.pct(share, 0)}</strong></span>${
        next ? `<span>Next: ${esc(skills[next[0]].label)} ${fmt.signedPct(next[1] / r.listed)}</span>` : ""
      }`;
    }

    el.result.innerHTML = `
      <p class="hint">${scope.length ? esc(scope.join(" · ")) : "All Werkstudent postings"}</p>
      ${
        none
          ? `<p class="result-big">—</p><p class="result-sub">Pick the skills you have to see how many postings you match.</p>`
          : `<p class="result-big">${fmt.pct(share, 0)}</p>
             <p class="result-sub">You match <strong>${fmt.int(r.matches)}</strong> of ${fmt.int(r.listed)} postings that list specific skills.</p>
             <div class="meter" aria-hidden="true"><div style="width:${share * 100}%"></div></div>`
      }
      ${
        none
          ? ""
          : `<div class="list-buttons">
               <button type="button" class="more" data-list="matched" ${r.matched.length ? "" : "disabled"}>See ${fmt.int(r.matched.length)} matching postings</button>
               ${r.near.length ? `<button type="button" class="link-btn" data-list="near">${fmt.int(r.near.length)} more are one skill away</button>` : ""}
             </div>`
      }
      ${pay}
      ${sugg}
      <p class="small-print">A match means you have all listed skills, or all but one in four. ${fmt.int(r.pool - r.listed)} of ${fmt.int(r.pool)} postings in this selection list no specific tools and aren't counted.</p>`;
  }

  // --- List of matching postings (titles come from postings.json, loaded on first use) ---

  const listState = { tab: "matched", sort: "newest", shown: LIST_PAGE };
  let postings = null;

  async function loadPostings() {
    if (postings) return postings;
    const res = await fetch("data/postings.json", { cache: "no-cache" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    // Both files come from the same build; if one is newer, positions don't line up.
    if (data.as_of !== data_as_of || data.rows.length !== jobs.length) throw new Error("data is being updated, please reload the page");
    postings = data;
    return postings;
  }

  async function openList(tab) {
    listState.tab = tab;
    listState.shown = LIST_PAGE;
    el.list.hidden = false;
    el.listBody.innerHTML = `<p class="empty">Loading postings…</p>`;
    el.list.scrollIntoView({ behavior: "smooth", block: "start" });
    try {
      await loadPostings();
      renderList();
    } catch (err) {
      el.listBody.innerHTML = `<p class="empty">Couldn't load the postings (${esc(err.message)}).</p>`;
    }
  }

  function renderList() {
    if (!postings || !lastResult) return;
    const r = lastResult;
    const items = listState.tab === "matched" ? r.matched.map((i) => [i, null]) : r.near;
    el.listTabs.innerHTML = `
      <button type="button" class="tab" data-tab="matched" aria-selected="${listState.tab === "matched"}">You match (${fmt.int(r.matched.length)})</button>
      <button type="button" class="tab" data-tab="near" aria-selected="${listState.tab === "near"}">One skill away (${fmt.int(r.near.length)})</button>`;

    const published = (i) => postings.rows[i][4] || "";
    const sorted = [...items].sort(([a], [b]) =>
      listState.sort === "pay"
        ? (jobs[b][3] ?? -1) - (jobs[a][3] ?? -1) || published(b).localeCompare(published(a))
        : published(b).localeCompare(published(a)),
    );
    const page = sorted.slice(0, listState.shown);
    el.listBody.innerHTML = page.length
      ? page.map(([i, missing]) => postingRow(i, missing)).join("")
      : `<p class="empty">${listState.tab === "matched" ? "No matches yet. Add skills or widen the filters." : "Nothing here: add skills first."}</p>`;
    el.listMore.hidden = sorted.length <= listState.shown;
    el.listMore.textContent = `Show more (${fmt.int(sorted.length - listState.shown)} left)`;
  }

  function postingRow(i, missing) {
    const [refnr, title, company, city, date] = postings.rows[i];
    const [cat, , german, pay] = jobs[i];
    const url = postings.url.replace("{refnr}", encodeURIComponent(refnr));
    const lang = german <= 1 ? `<span class="badge strong">German: ${german === 0 ? "not needed" : "a plus"}</span>` : "";
    const need = missing
      ? `<span class="badge need">Learn ${missing.map((s) => esc(skills[s].label)).join(" or ")}</span>`
      : "";
    return `<div class="job">
      <a href="${esc(url)}" target="_blank" rel="noopener">${esc(title)}</a>
      <div class="meta">${esc(company)} · ${esc(city || "—")} · ${esc(labels.category(categories[cat] ?? "other"))}${date ? ` · posted ${esc(fmt.shortDate(date))}` : ""}</div>
      <div class="side">${need}${lang}${pay != null ? `<span class="pay">${fmt.eur(pay)}/h</span>` : ""}</div>
    </div>`;
  }

  function update() {
    renderChips();
    renderResult();
    if (!el.list.hidden) renderList();
    const ids = [...state.selected].map((i) => skills[i].id).join(",");
    const url = new URL(location.href);
    url.search = ids ? `?skills=${ids}` : "";
    history.replaceState(null, "", url);
  }

  update();
}
