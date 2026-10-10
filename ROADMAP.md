# Roadmap

Growing Werkstudent Radar into a portfolio project across data engineering,
statistics, NLP and product work. Tick items off as they land (one commit per
step), so progress is visible here and not only in the commit history.

Rules for every phase:
- Incremental: no rewrites. `docs/data/*.json` stay backward compatible (only new
  files or new fields; `checker.json` rows never reordered).
- No frontend framework or build step; new `<script>`/`<link>`/imports carry `?v=dev`.
- New Python dependencies go into `requirements.txt`; the daily run stays fast.
- The site gets aggregates only, never job texts.
- Commits only after the owner's OK; the owner pushes.

## Decisions

- **History store (Phase 1).** A daily-updated binary SQLite file would change on
  most pages every day (every active posting's `last_seen` moves) and grow the git
  repository by megabytes a day. So the committed source of truth is plain text:
  `data/jobs.csv` (one row per posting, already kept forever) plus small,
  append-mostly CSVs in `data/history/`. `data/history.sqlite` is rebuilt from
  them in seconds (`python -m radar.history`) and is git-ignored.

## Phase 1 — Data engineering: history

- [x] SQLite history database `data/history.sqlite` (built from committed CSVs, see
      Decisions): `postings` keyed by refnr (first_seen, last_seen, field, city,
      lat/lon, pay, German requirement, skills) plus `scans` (one row per collection
      day and source) and `online` (intervals of consecutive scans a posting was
      seen in). Daily run upserts; postings missing today keep their last_seen.
- [x] Backfill from what exists: scans from `history.csv`/`history.json`, intervals
      from `jobs.csv` first_seen/last_seen.
- [x] New aggregate file for the site (daily postings online / new / gone), no raw texts.
- [x] Daily workflow runs the history step and commits `data/history/`.

## Phase 2 — Quality: tests + data checks

- [x] pytest for pay parsing ("17,50 € pro Stunde" etc.), skill/German detection,
      dedup and the upsert logic (extend the existing 133 tests where they already cover it).
- [x] Data-quality checks in the pipeline: fail the run if the posting count drops or
      jumps >50% vs. the 7-day median, required API fields are missing, or pay values
      fall outside a sane range. A failing run opens/updates the GitHub issue.
- [x] Tests in CI on every push (`tests.yml`, now without the data-only path filter) and a
      status badge in the README (both badges already existed).

## Phase 3 — Statistics

- [x] Bootstrap 95% confidence intervals (2000 resamples, fixed seed) for every median
      pay shown; shown as a subtle range ("€16.50 · 95% CI €15.40–17.60"); medians with
      a very wide CI or n<10 hidden (current n≥10 rule stays).
- [x] Posting lifetime from first_seen/last_seen: Kaplan–Meier curve (still-online
      postings censored), median days online overall and by field; new chart in Trends.
      Age is counted from the publication date with delayed entry (postings are only
      observed from their first scan); Bundesagentur postings only.
- [x] Skill co-occurrence: for each skill, top co-occurring skills with lift.

## Phase 4 — Product: skill gap + alerts

- [ ] "Check your skills": skill-gap suggestions ("learn X and Y to qualify for N more
      jobs"), client-side from `checker.json`, greedy by marginal gain.
- [ ] RSS feeds generated daily: all new postings and one per field (title, company,
      city, link to the original, no job text); small "Subscribe" control in the UI.

## Phase 5 — NLP experiment

- [ ] `experiments/`: skill extraction with multilingual sentence embeddings or a small
      zero-shot model vs. the current rules on the 100 labelled postings (labels are
      AI-made, see `data/eval/LABELS.md`); precision/recall/F1 per skill and overall.
- [ ] Recommendation: replace/combine with the rules only if clearly better. The daily
      pipeline is not touched in this phase.

## Phase 6 — Extra frontend

- [ ] Optional SQL playground: DuckDB-WASM lazy-loaded from jsDelivr only when opened,
      over a Parquet export of aggregated postings (no texts); 3–4 example queries.
- [ ] Lighthouse CI (desktop) in GitHub Actions; Performance, Accessibility,
      Best Practices ≥ 90.
- [ ] German/English UI toggle: strings in one dictionary, language in the URL.

## Phase 7 — Packaging

- [ ] README: Mermaid architecture diagram (BA API → pipeline → SQLite → build →
      docs/ → Pages), screenshots, live link, key numbers (postings per day, days of
      history, skill-detection precision/recall) and a "Methods" section (bootstrap,
      Kaplan–Meier, lift).
