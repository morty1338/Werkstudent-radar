// SQL playground: DuckDB compiled to WebAssembly, running in the browser on
// data/postings.parquet (every posting ever seen: features, pay, skills; no job
// texts) and data/skills.parquet (skill labels). DuckDB-WASM comes from jsDelivr
// and is only loaded when someone opens the playground.

import { esc, fmt } from "./charts.js?v=dev";

const DUCKDB = "https://cdn.jsdelivr.net/npm/@duckdb/duckdb-wasm@1.29.0";
const MAX_ROWS = 200;

export const EXAMPLES = [
  {
    title: "Median pay by field",
    sql: `-- Postings online today; each role (company + title) counted once, as on the site
WITH roles AS (
  SELECT * FROM postings
  WHERE online
  QUALIFY row_number() OVER (PARTITION BY company, lower(title) ORDER BY refnr) = 1
)
SELECT field_label AS field, count(*) AS roles, median(pay) AS median_pay
FROM roles
WHERE pay IS NOT NULL
GROUP BY ALL
HAVING count(*) >= 10
ORDER BY median_pay DESC;`,
  },
  {
    title: "Skills in jobs without German",
    sql: `SELECT s.label AS skill, count(*) AS postings
FROM postings p, unnest(p.skills) AS u(skill)
JOIN skills s ON s.id = u.skill
WHERE p.online AND p.german IN ('none', 'plus')
GROUP BY ALL
ORDER BY postings DESC
LIMIT 15;`,
  },
  {
    title: "Best-paid skills",
    sql: `SELECT s.label AS skill,
       count(*) AS with_pay,
       median(p.pay) AS median_pay
FROM postings p, unnest(p.skills) AS u(skill)
JOIN skills s ON s.id = u.skill
WHERE p.online AND p.pay IS NOT NULL
GROUP BY ALL
HAVING count(*) >= 20
ORDER BY median_pay DESC
LIMIT 10;`,
  },
  {
    title: "IT jobs from €18/h by city",
    sql: `SELECT city, count(*) AS jobs, round(avg(pay), 2) AS avg_pay
FROM postings
WHERE online AND field = 'it' AND pay >= 18 AND city IS NOT NULL
GROUP BY city
ORDER BY jobs DESC
LIMIT 10;`,
  },
];

let ready = null;

// Start DuckDB in a web worker and register the Parquet files as tables.
function start() {
  ready ??= (async () => {
    const duckdb = await import(`${DUCKDB}/+esm`);
    const bundle = await duckdb.selectBundle(duckdb.getJsDelivrBundles());
    // Workers can't be started from another origin directly; wrap the script in a blob.
    const workerUrl = URL.createObjectURL(new Blob([`importScripts("${bundle.mainWorker}");`], { type: "text/javascript" }));
    const db = new duckdb.AsyncDuckDB(new duckdb.ConsoleLogger(duckdb.LogLevel.WARNING), new Worker(workerUrl));
    await db.instantiate(bundle.mainModule, bundle.pthreadWorker);
    URL.revokeObjectURL(workerUrl);
    const conn = await db.connect();
    for (const name of ["postings", "skills"]) {
      const url = new URL(`data/${name}.parquet`, location.href).href;
      await db.registerFileURL(`${name}.parquet`, url, duckdb.DuckDBDataProtocol.HTTP, false);
      await conn.query(`CREATE VIEW ${name} AS SELECT * FROM '${name}.parquet'`);
    }
    return conn;
  })();
  return ready;
}

// Arrow values to something printable: BigInt counts, dates (milliseconds in Arrow), lists.
function cell(v, type = "") {
  if (v == null) return "";
  if (/^(Date|Timestamp)/.test(type)) return new Date(Number(v)).toISOString().slice(0, type.startsWith("Date") ? 10 : 16).replace("T", " ");
  if (typeof v === "bigint") return fmt.int(Number(v));
  if (typeof v === "number") return Number.isInteger(v) ? fmt.int(v) : String(Math.round(v * 100) / 100);
  if (v instanceof Date) return v.toISOString().slice(0, 10);
  if (typeof v === "object" && typeof v.toArray === "function") return v.toArray().map(cell).join(", ");
  return String(v);
}

export function initSql() {
  const box = document.getElementById("sql");
  const input = document.getElementById("sql-input");
  const run = document.getElementById("sql-run");
  const out = document.getElementById("sql-out");
  const status = document.getElementById("sql-status");

  document.getElementById("sql-examples").innerHTML = EXAMPLES
    .map((e, i) => `<button type="button" class="chip" data-example="${i}">${esc(e.title)}</button>`)
    .join("");
  input.value = EXAMPLES[0].sql;

  async function execute() {
    run.disabled = true;
    status.textContent = ready ? "Running…" : "Loading DuckDB (about 7 MB, once)…";
    try {
      const conn = await start();
      const t0 = performance.now();
      const table = await conn.query(input.value);
      const ms = Math.round(performance.now() - t0);
      const cols = table.schema.fields.map((f) => f.name);
      const types = table.schema.fields.map((f) => String(f.type));
      const rows = table.toArray().slice(0, MAX_ROWS);
      status.textContent = `${fmt.int(table.numRows)} row${table.numRows === 1 ? "" : "s"} in ${ms} ms${table.numRows > MAX_ROWS ? ` · first ${MAX_ROWS} shown` : ""}`;
      out.innerHTML = `<table><thead><tr>${cols.map((c) => `<th>${esc(c)}</th>`).join("")}</tr></thead><tbody>${rows
        .map((r) => `<tr>${cols.map((c, k) => `<td>${esc(cell(r[c], types[k]))}</td>`).join("")}</tr>`)
        .join("")}</tbody></table>`;
    } catch (err) {
      status.textContent = "";
      out.innerHTML = `<p class="sql-error">${esc(err.message || String(err))}</p>`;
    } finally {
      run.disabled = false;
    }
  }

  run.addEventListener("click", execute);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      execute();
    }
  });
  document.getElementById("sql-examples").addEventListener("click", (e) => {
    const b = e.target.closest("[data-example]");
    if (!b) return;
    input.value = EXAMPLES[Number(b.dataset.example)].sql;
    execute();
  });
  // Opening the playground loads DuckDB and runs the first example.
  box.addEventListener("toggle", () => box.open && !ready && execute());
}
