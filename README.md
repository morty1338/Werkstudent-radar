# Werkstudent Radar

The German working-student job market in numbers: real hourly rates, which
skills are in demand, and how many jobs you can get without speaking German.

Data source: the public job search of the
[Bundesagentur für Arbeit](https://www.arbeitsagentur.de/jobsuche/).
Only Werkstudent postings in Germany are collected.

> Work in progress. Currently: daily collection of raw postings.

## Quick start

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m radar.collect
```

This pages through the job search API for all Werkstudent postings in Germany
and writes them to `data/raw/<date>/`:

| File | Content |
|------|---------|
| `listings.jsonl.gz` | one raw search result per line, de-duplicated by reference number |
| `run.json` | run metadata: endpoint, results per query, counts, duration |

Raw data stays local (`data/raw/` is git-ignored). Job descriptions belong to
the employers and are never published; the project will only publish
aggregated statistics and links to the original postings.

## Project layout

```
radar/collect.py   fetch all Werkstudent postings from the API
data/raw/          local raw dumps, one folder per day (not committed)
```
