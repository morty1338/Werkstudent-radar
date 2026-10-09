# Werkstudent Radar

[![Daily data update](https://github.com/morty1338/werkstudent-radar/actions/workflows/daily.yml/badge.svg)](https://github.com/morty1338/werkstudent-radar/actions/workflows/daily.yml)
[![Tests](https://github.com/morty1338/werkstudent-radar/actions/workflows/tests.yml/badge.svg)](https://github.com/morty1338/werkstudent-radar/actions/workflows/tests.yml)

The German working-student job market in numbers: real hourly rates, which
skills are in demand, and how many jobs you can get without speaking German.

Data source: the public job search of the
[Bundesagentur für Arbeit](https://www.arbeitsagentur.de/jobsuche/).
Only Werkstudent postings in Germany are collected.

**Live: [morty1338.github.io/werkstudent-radar](https://morty1338.github.io/werkstudent-radar/)**, updated every morning.

- **Pay**: median hourly rate by field and city, from the rates stated in postings
- **German**: how many postings are open to non-German speakers, with the full list
- **Skills**: what's asked for, by field and city, and which skills come with higher pay
- **Check your skills**: tick what you can do, see the share of postings you match and which skill opens the most new ones
- **Study programmes**: Wirtschaftsinformatik, Informatik, BWL, Wirtschaftsingenieurwesen and more
- **Trends**: daily snapshots from 9 Oct 2026 on

## Quick start

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m radar.collect   # 1. raw search results (~30 s)
.venv/bin/python -m radar.enrich    # 2. job texts -> features in data/jobs.csv (~2 min on the first run)
.venv/bin/python -m radar.build     # 3. SQL aggregates -> docs/data/*.json + data/history.csv
```

`collect` pages through the job search API for all Werkstudent postings in Germany
and writes them to `data/raw/<date>/`:

| File | Content |
|------|---------|
| `listings.jsonl.gz` | one raw search result per line, de-duplicated by reference number |
| `run.json` | run metadata: endpoint, results per query, counts, duration |

`enrich` fetches the full text only for postings that are new (or were tagged
by an older rule version), caches it locally in `details.jsonl.gz` and turns
it into features. Raw data stays local (`data/raw/` is git-ignored). Job
descriptions belong to the employers and are never published: `data/jobs.csv`
holds only derived features plus the reference number, which links to the
original posting at `https://www.arbeitsagentur.de/jobsuche/jobdetail/<refnr>`.

## `data/jobs.csv`

One row per Werkstudent posting ever seen.

| Column | Meaning |
|--------|---------|
| `refnr`, `title`, `company`, `hauptberuf` | posting metadata from the API |
| `city`, `region` | first location, city name normalised |
| `category` | job field from title / occupation (`it`, `data`, `marketing`, `finance`, `engineering`, `retail`, …) |
| `lang` | language the posting is written in (`de` / `en`) |
| `german` | `required` (e.g. "fließend Deutsch", "German C1"), `plus` ("von Vorteil", "nice to have"), `none` ("English only", or an English posting that never asks for German), `implicit` (German posting that doesn't mention it) |
| `english` | 1 if English is required |
| `pay_min`, `pay_max`, `pay_src` | hourly pay in € from the API's salary fields (`ba`) or the text (`text`, e.g. "17,50 € brutto pro Stunde") |
| `hours` | hours per week, if stated |
| `skills` | skill ids from [`radar/skills.py`](radar/skills.py), `\|`-separated |
| `majors` | study programmes mentioned (`wiinf`, `inf`, `bwl`, `wiing`, …) |
| `remote`, `external` | home office possible; posting links to an external site |
| `published`, `first_seen`, `last_seen` | first publication date; first/last day the collector saw it |
| `detail_ok`, `xv` | text was available; extractor version used |

### How features are extracted

- **Skills**: a dictionary of ~180 skills with German and English synonyms
  (`SQL`, `Power BI`, `SAP FI/CO`, `Buchhaltung`/`accounting`, …). Words that
  are also common language ("Excel" vs. "excel at", "React" vs. "react to")
  are matched case-sensitively. Broad domain terms ("Einkauf", "Vertrieb",
  "Recruiting") only count next to a requirement cue like "Kenntnisse",
  "Erfahrung" or "experience", so benefits such as "5% Einkaufsrabatt" or an
  "Recruiting-Team" contact line don't count.
- **German**: regex rules for requirement phrases, scoped to the list item they
  appear in, so in "Sehr gute Deutschkenntnisse, Englisch von Vorteil" the
  "von Vorteil" is attributed to English.
- **Pay**: an amount only counts as hourly pay when the marker sits right next
  to it ("16 €/h", "Stundenlohn von 16 €"), and only between 12 and 60 €.

## Aggregation (`radar/build.py`, `radar/sql/`)

`build` loads `jobs.csv` into an in-memory SQLite database
([schema](radar/sql/schema.sql): `jobs`, link tables `job_skills` /
`job_majors`, label tables) and runs one SQL file per output. Medians and
quartiles come from a custom `percentile(value, q)` aggregate; top-N per group
uses window functions.

Two choices keep the numbers honest:

- **Pay counts each role once.** Some employers post the same role in dozens of
  cities (one had 97 copies, all at minimum wage). Pay figures use one posting
  per company + title (per city for city figures); job counts still count every
  posting.
- **Medians need breadth.** A median is shown only with at least 10 roles from 5
  employers. Each group also reports `pay_employers` and `top_employer_share`;
  headline comparisons ("best-paid city") skip groups where one employer supplies
  more than 35% of the sample.

Outputs:

| File | Content |
|------|---------|
| `docs/data/summary.json` | totals, German requirements, pay histogram, fields, cities, skills, study programmes (with example postings), all postings open to non-German speakers, headline insights |
| `docs/data/checker.json` | per posting: field, city, German level, pay and skill indices, for the in-browser skill checker |
| `docs/data/history.json` | daily series built from `data/history.csv` |
| `data/history.csv` | one row per day × metric (`total`, `category`, `city`, `skill`, `major`, `german`). Which postings were online on a given day can't be reconstructed later, so this is collected from day one. |

## Automation

[`daily.yml`](.github/workflows/daily.yml) runs every morning (04:23 UTC) and
can be started by hand from the Actions tab:

1. `collect` → `enrich` → `build`. Only new postings need their text, so a
   normal day takes about a minute.
2. Commits `data/jobs.csv`, `data/history.csv` and `docs/data/` as
   `github-actions[bot]` ("Update data for YYYY-MM-DD").
3. If any step fails, opens an issue "Daily data update failed" with the last
   40 log lines and a link to the run (GitHub notifies by e-mail). Further
   failures comment on the same issue; the next successful run closes it.

The run fails on purpose when the data looks wrong: an API path answering
403/404 (old versions get switched off), fewer than 1,000 postings, fewer than
half of the previous day's, or more than half of the job texts missing.

[`pages.yml`](.github/workflows/pages.yml) publishes `docs/` to GitHub Pages.
It runs on pushes that change the site and is called by the daily workflow
after each data update, because commits pushed with `GITHUB_TOKEN` don't
trigger Pages builds on their own.

[`tests.yml`](.github/workflows/tests.yml) runs the test suite on every push
and pull request.

## Website (`docs/`)

A static page in plain HTML, CSS and JavaScript (no framework, no build step,
no third-party scripts), so it loads instantly and costs nothing to host. It
reads the three JSON files in `docs/data/`; the skill checker runs entirely in
the browser on `checker.json`. Charts are hand-made HTML/SVG with light and
dark themes. To preview locally:

```bash
python3 -m http.server --directory docs
```

## Accuracy

The extraction rules are heuristics, so they are measured against 100 labelled
postings ([`radar/evaluate.py`](radar/evaluate.py)): 70 drawn at random, 20 that
the rules call "open without German" and 10 whose pay was found in the text.
Labelling was blind (posting text only, no predictions) and was done by an AI
assistant in two passes, not by a human; see
[`data/eval/LABELS.md`](data/eval/LABELS.md) for exactly how.

| Check | Baseline (rules v2) | After fixes (v3)\* |
|---|---|---|
| Needs German: yes / no (random 70) | 100% | 100% |
| German level: required / plus / none / not mentioned | 94% | 99% |
| Shown as "open without German" and really is | **68%** (15/22) | 100% (15/15) |
| Hourly pay found: precision / recall | 100% / 100% | 100% / 100% |
| Pay amount correct | 95% (18/19) | 100% (19/19) |
| Skills, 14 common ones: precision / recall | 99% / 96% | 99% / 97% |
| Job field | 64% | 79% |

\* The rules were fixed using the baseline disagreements, so the v3 column is
measured on postings the rules have now "seen" and is optimistic. The baseline
column is the honest one. Biggest lesson: the German rule confused "Russisch
von Vorteil" or "French is beneficial" with German being optional, which
inflated the share of English-friendly jobs. Job field remains the weakest
part: many postings sit between two fields ("Datenanalyse & Finance
Operations").

Full reports: [baseline](data/eval/report_baseline.md),
[current](data/eval/report.md). Every fixed error became a test case:

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest                   # 109 rule and SQL tests
.venv/bin/python -m radar.evaluate report    # needs the local sample texts
```

## Project layout

```
radar/api.py       small client for the BA job search API (retries, errors)
radar/collect.py   fetch all Werkstudent postings -> data/raw/<date>/
radar/enrich.py    fetch texts for new postings, extract features -> data/jobs.csv
radar/extract.py   feature extraction rules
radar/skills.py    skill dictionary (German + English synonyms)
radar/build.py     load jobs.csv into SQLite, run radar/sql/*.sql, write JSON
radar/sql/         schema and one query per output
radar/evaluate.py  accuracy check against labelled postings
eval/label.html    blind labelling form
tests/             rule tests on made-up snippets, SQL tests on a tiny fixture
data/jobs.csv      extracted features (committed)
data/history.csv   daily metric snapshots (committed)
data/eval/         evaluation labels and reports (job texts stay local)
docs/              the website (index.html, assets/)
docs/data/         JSON consumed by the website
data/raw/          local raw dumps, one folder per day (not committed)
```
