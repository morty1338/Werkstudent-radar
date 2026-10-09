"""Aggregate data/jobs.csv with SQL and write the JSON files the website reads.

Usage:
    python -m radar.build

Loads jobs.csv into an in-memory SQLite database (schema in sql/schema.sql),
runs the queries in sql/*.sql and writes:

    docs/data/summary.json   headline numbers, pay, German, fields, cities, skills, majors
    docs/data/checker.json   compact per-job skill lists for the in-browser skill checker
    docs/data/history.json   daily time series for the trend charts
    data/history.csv         today's snapshot appended (one row per metric and day)

The snapshot matters: which postings were online on a given day, and what they
paid, can't be reconstructed later, so the history is built up day by day.
"""

import csv
import json
import os
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone

from .extract import CATEGORIES, MAJORS
from .skills import SKILLS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SQL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sql")
JOBS_CSV = os.path.join(ROOT, "data", "jobs.csv")
HISTORY_CSV = os.path.join(ROOT, "data", "history.csv")
OUT_DIR = os.path.join(ROOT, "docs", "data")

MIN_PAY_SAMPLE = 10     # don't report a median pay based on fewer roles than this…
MIN_PAY_EMPLOYERS = 5   # …or on fewer distinct employers
MAX_EMPLOYER_SHARE = 0.35  # insights skip groups where one employer supplies more of the sample
MIN_CITY_JOBS = 15
MIN_CHECKER_SKILL_JOBS = 5
TOP_CITIES_HISTORY = 20
HISTORY_COLUMNS = ["date", "dim", "key", "jobs", "with_pay", "median_pay", "no_german"]
JOB_URL = "https://www.arbeitsagentur.de/jobsuche/jobdetail/{refnr}"


# --- SQLite setup --------------------------------------------------------------

class Percentile:
    """SQL aggregate percentile(value, q) with linear interpolation; ignores NULLs."""

    def __init__(self):
        self.values, self.q = [], None

    def step(self, value, q):
        self.q = q
        if value is not None:
            self.values.append(float(value))

    def finalize(self):
        if not self.values:
            return None
        v = sorted(self.values)
        pos = (len(v) - 1) * self.q
        lo = int(pos)
        hi = min(lo + 1, len(v) - 1)
        return round(v[lo] + (v[hi] - v[lo]) * (pos - lo), 2)


def sql(name):
    with open(os.path.join(SQL_DIR, f"{name}.sql"), encoding="utf-8") as f:
        return f.read()


def _num(s, cast=float):
    return cast(s) if s not in (None, "") else None


def load_db(jobs_csv=JOBS_CSV):
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.create_aggregate("percentile", 2, Percentile)
    db.executescript(sql("schema"))

    db.executemany("INSERT INTO skills VALUES (?, ?, ?)", [(sid, label, grp) for sid, label, grp, _ in SKILLS])
    db.executemany("INSERT INTO majors VALUES (?, ?)", [(mid, label) for mid, label, _ in MAJORS])
    db.executemany("INSERT INTO categories VALUES (?, ?)", [(cid, label) for cid, label, _ in CATEGORIES] + [("other", "Other")])

    with open(jobs_csv, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    jobs, job_skills, job_majors = [], [], []
    for r in rows:
        lo, hi = _num(r["pay_min"]), _num(r["pay_max"])
        jobs.append((
            r["refnr"], r["title"], r["company"], r["city"], r["region"], r["category"],
            r["lang"], r["german"], _num(r["english"], int), lo, hi,
            round((lo + hi) / 2, 2) if lo is not None else None,
            r["pay_src"], _num(r["hours"], int), _num(r["remote"], int), _num(r["external"], int),
            r["published"], r["first_seen"], r["last_seen"], _num(r["detail_ok"], int) or 0,
        ))
        job_skills += [(r["refnr"], s) for s in r["skills"].split("|") if s]
        job_majors += [(r["refnr"], m) for m in r["majors"].split("|") if m]
    db.executemany(f"INSERT INTO jobs VALUES ({','.join('?' * 20)})", jobs)
    db.executemany("INSERT INTO job_skills VALUES (?, ?)", job_skills)
    db.executemany("INSERT INTO job_majors VALUES (?, ?)", job_majors)
    return db


def query(db, name, **params):
    return [dict(r) for r in db.execute(sql(name), params)]


def hide_small_medians(rows):
    """Null out medians based on too few roles or employers; keep the sample size visible."""
    for r in rows:
        if (r.get("with_pay") or 0) < MIN_PAY_SAMPLE or (r.get("pay_employers") or 0) < MIN_PAY_EMPLOYERS:
            r["median_pay"] = None
    return rows


def representative(rows):
    """Groups whose median isn't dominated by a single employer (used for headline claims)."""
    return [r for r in rows if r["median_pay"] and (r.get("top_employer_share") or 1) <= MAX_EMPLOYER_SHARE]


def share(part, whole):
    return round(part / whole, 4) if whole else None


# --- Outputs -----------------------------------------------------------------------

def build_summary(db):
    t = query(db, "totals")[0]
    totals = {
        **t,
        "pay_share": share(t["with_pay"], t["jobs"]),
        "no_german_share": share(t["no_german"], t["tagged"]),
        "english_posting_share": share(t["english_postings"], t["tagged"]),
        "remote_share": share(t["remote"], t["jobs"]),
    }

    categories = hide_small_medians(query(db, "categories"))
    top_by_cat = defaultdict(list)
    for r in query(db, "top_skills_by", n=6):
        top_by_cat[r["grp"]].append(r["skill"])
    for c in categories:
        c["top_skills"] = top_by_cat.get(c["key"], [])

    cities = hide_small_medians(query(db, "cities", min_jobs=MIN_CITY_JOBS))
    skills = hide_small_medians(query(db, "skills"))

    majors = hide_small_medians(query(db, "majors"))
    breakdown = defaultdict(lambda: defaultdict(list))
    for r in query(db, "major_breakdown", n=6):
        breakdown[r["major"]][r["dim"]].append({"key": r["key"], "jobs": r["jobs"]})
    examples = defaultdict(list)
    for r in query(db, "major_examples", n=8):
        examples[r.pop("major")].append(with_url({k: v for k, v in r.items() if k != "rn"}))
    for m in majors:
        m.update({
            "categories": breakdown[m["id"]]["category"],
            "cities": breakdown[m["id"]]["city"],
            "skills": breakdown[m["id"]]["skill"],
            "examples": examples[m["id"]],
        })

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "as_of": t["as_of"],
        "source": {
            "name": "Bundesagentur für Arbeit – Jobbörse",
            "url": "https://www.arbeitsagentur.de/jobsuche/",
            "note": "Werkstudent postings in Germany; job texts are analysed but not published.",
        },
        "method": {
            "pay": "Hourly pay from the posting's salary fields or its text. Each role (company + title) "
                   "counts once in pay figures, so an employer posting one role in many cities doesn't dominate. "
                   "Medians need at least 10 roles from 5 employers; headline comparisons skip groups where "
                   "one employer supplies more than 35% of the sample.",
            "no_german": "German is not mentioned in an English posting, is explicitly not required, or is only 'a plus'.",
        },
        "thresholds": {
            "min_pay_sample": MIN_PAY_SAMPLE,
            "min_pay_employers": MIN_PAY_EMPLOYERS,
            "max_employer_share": MAX_EMPLOYER_SHARE,
        },
        "totals": totals,
        "german": query(db, "german"),
        "pay_histogram": query(db, "pay_histogram"),
        "categories": categories,
        "cities": cities,
        "skills": skills,
        "majors": majors,
        "english_friendly": [with_url(r) for r in query(db, "english_friendly")],
        "insights": insights(totals, categories, cities, skills),
    }


def with_url(row):
    return {**row, "url": JOB_URL.format(refnr=row["refnr"])}


def insights(totals, categories, cities, skills):
    """Numbers behind the headline sentences; the site turns them into text."""
    by_cat = {c["key"]: c for c in categories}
    out = {}

    it, mk = by_cat.get("it"), by_cat.get("marketing")
    if it and mk and it in representative(categories) and mk in representative(categories):
        out["it_vs_marketing"] = {
            "it": it["median_pay"], "marketing": mk["median_pay"],
            "premium": round(it["median_pay"] / mk["median_pay"] - 1, 4),
        }

    paid_cats = representative(categories)
    if paid_cats:
        top, low = max(paid_cats, key=lambda c: c["median_pay"]), min(paid_cats, key=lambda c: c["median_pay"])
        out["best_paid_category"] = {"key": top["key"], "median_pay": top["median_pay"], "with_pay": top["with_pay"]}
        out["lowest_paid_category"] = {"key": low["key"], "median_pay": low["median_pay"], "with_pay": low["with_pay"]}

    paid_cities = representative(cities)
    if paid_cities:
        top = max(paid_cities, key=lambda c: c["median_pay"])
        out["best_paid_city"] = {"city": top["city"], "median_pay": top["median_pay"], "with_pay": top["with_pay"]}

    overall = totals["median_pay"]
    paid_skills = [s for s in representative(skills) if s["with_pay"] >= 2 * MIN_PAY_SAMPLE]
    if paid_skills and overall:
        top = max(paid_skills, key=lambda s: s["median_pay"])
        out["best_paid_skill"] = {
            "id": top["id"], "median_pay": top["median_pay"], "with_pay": top["with_pay"],
            "premium": round(top["median_pay"] / overall - 1, 4),
        }

    open_cats = [c for c in categories if c["jobs"] >= 100]
    if open_cats:
        top = max(open_cats, key=lambda c: c["no_german_share"] or 0)
        out["most_international_category"] = {"key": top["key"], "share": top["no_german_share"], "jobs": top["no_german"]}

    berlin = next((c for c in cities if c["city"] == "Berlin"), None)
    if berlin:
        out["berlin"] = {k: berlin[k] for k in ("jobs", "median_pay", "with_pay", "no_german", "no_german_share", "it_data_jobs")}
    return out


def build_checker(db, summary):
    """Compact job list for the skill checker: indices instead of repeated strings."""
    skills = [s for s in summary["skills"] if s["jobs"] >= MIN_CHECKER_SKILL_JOBS]
    skill_idx = {s["id"]: i for i, s in enumerate(skills)}
    cats = [c["key"] for c in summary["categories"]]
    cat_idx = {k: i for i, k in enumerate(cats)}
    cities = [c["city"] for c in summary["cities"]]
    city_idx = {k: i for i, k in enumerate(cities)}
    german_codes = ["none", "plus", "implicit", "required"]

    jobs = []
    for r in query(db, "checker_jobs"):
        ids = sorted(skill_idx[s] for s in (r["skills"] or "").split("|") if s in skill_idx)
        jobs.append([
            cat_idx.get(r["category"], -1),
            city_idx.get(r["city"], -1),
            german_codes.index(r["german"]) if r["german"] in german_codes else 2,
            r["pay"],
            ids,
        ])
    return {
        "as_of": summary["as_of"],
        "fields": ["category", "city", "german", "pay", "skills"],
        "skills": [{"id": s["id"], "label": s["label"], "group": s["group"], "jobs": s["jobs"]} for s in skills],
        "categories": cats,
        "cities": cities,
        "german": german_codes,
        "jobs": jobs,
    }


def update_history(db, as_of, path=HISTORY_CSV):
    """Replace today's rows in data/history.csv and return all rows."""
    rows = []
    if os.path.exists(path):
        with open(path, newline="", encoding="utf-8") as f:
            rows = [r for r in csv.DictReader(f) if r["date"] != as_of]
    for r in query(db, "history_snapshot", top_cities=TOP_CITIES_HISTORY):
        rows.append({"date": as_of, **{k: ("" if v is None else v) for k, v in r.items()}})
    rows.sort(key=lambda r: (r["date"], r["dim"], r["key"]))
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=HISTORY_COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    return rows


def build_history(rows):
    """Time series for the site: full metrics for the total, job counts per dimension."""
    dates = sorted({r["date"] for r in rows})
    pos = {d: i for i, d in enumerate(dates)}
    series = defaultdict(lambda: [None] * len(dates))
    for r in rows:
        i = pos[r["date"]]
        name = f'{r["dim"]}:{r["key"]}'
        series[f"{name}:jobs"][i] = int(r["jobs"])
        if r["dim"] == "total":
            series[f"{name}:median_pay"][i] = _num(r["median_pay"])
            series[f"{name}:with_pay"][i] = int(r["with_pay"])
            series[f"{name}:no_german"][i] = int(r["no_german"] or 0)
    return {"dates": dates, "series": dict(sorted(series.items()))}


def write_json(name, data):
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    return path


def main():
    db = load_db()
    summary = build_summary(db)
    checker = build_checker(db, summary)
    history = build_history(update_history(db, summary["as_of"]))

    for name, data in [("summary.json", summary), ("checker.json", checker), ("history.json", history)]:
        path = write_json(name, data)
        print(f"wrote {os.path.relpath(path, ROOT)} ({os.path.getsize(path) / 1024:.0f} KB)")

    t = summary["totals"]
    print(f"{summary['as_of']}: {t['jobs']} jobs, median {t['median_pay']} €/h (n={t['with_pay']}), "
          f"{t['no_german_share']:.1%} without German, {len(history['dates'])} day(s) of history")


if __name__ == "__main__":
    main()
