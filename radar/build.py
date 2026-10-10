"""Aggregate data/jobs.csv with SQL and write the JSON files the website reads.

Usage:
    python -m radar.build

Loads jobs.csv into an in-memory SQLite database (schema in sql/schema.sql),
runs the queries in sql/*.sql and writes:

    docs/data/summary.json   headline numbers, pay, German, fields, cities, skills, majors
    docs/data/checker.json   compact per-job skill lists for the in-browser skill checker
    docs/data/postings.json  title, company and city per checker job (loaded on demand)
    docs/data/history.json   daily time series for the trend charts
    docs/data/lifetimes.json how long postings stay online (Kaplan–Meier), overall and by field
    docs/data/cooccurrence.json  skills asked for together, with lift
    docs/data/og.png         social preview image with today's headline numbers
    docs/data/patterns.json  skill and study-programme rules for analysing a CV in the browser
    data/history.csv         today's snapshot appended (one row per metric and day)

The snapshot matters: which postings were online on a given day, and what they
paid, can't be reconstructed later, so the history is built up day by day.
"""

import csv
import json
import os
import sqlite3
from collections import defaultdict
from datetime import date, datetime, timezone

from . import og_image, patterns, stats
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
MAX_CI_REL_WIDTH = 0.25   # hide a median whose 95% CI is wider than a quarter of it
MIN_CITY_JOBS = 15
MIN_CHECKER_SKILL_JOBS = 5
TOP_CITIES_HISTORY = 20
MIN_AT_RISK = 30        # lifetime curves stop where fewer postings are still observed
MIN_FIELD_EVENTS = 10   # a field's median lifetime needs at least this many postings gone
COOC_MIN_PAIR = 5       # skill pairs need this many postings together…
COOC_TOP = 6            # …and each skill lists this many partners
HISTORY_COLUMNS = ["date", "dim", "key", "jobs", "with_pay", "median_pay", "no_german", "median_pay_lo", "median_pay_hi"]
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


class MedianCI:
    """SQL aggregate median_ci(value, bound): bound 0 gives the lower and 1 the upper end
    of the bootstrap 95% confidence interval of the median; ignores NULLs. Both ends
    come from one bootstrap run, cached by the group's values."""

    _cache = {}

    def __init__(self):
        self.values, self.bound = [], 0

    def step(self, value, bound):
        self.bound = bound
        if value is not None:
            self.values.append(float(value))

    def finalize(self):
        if not self.values:
            return None
        key = tuple(sorted(self.values))
        if key not in MedianCI._cache:
            MedianCI._cache[key] = stats.bootstrap_median_ci(key)
        return MedianCI._cache[key][self.bound]


def sql(name):
    with open(os.path.join(SQL_DIR, f"{name}.sql"), encoding="utf-8") as f:
        return f.read()


def _num(s, cast=float):
    return cast(s) if s not in (None, "") else None


def load_db(jobs_csv=JOBS_CSV):
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.create_aggregate("percentile", 2, Percentile)
    db.create_aggregate("median_ci", 2, MedianCI)
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
            r["refnr"], r["title"], r["company"], r["city"], r["region"],
            _num(r.get("lat")), _num(r.get("lon")), r["category"],
            r["lang"], r["german"], _num(r["english"], int), lo, hi,
            round((lo + hi) / 2, 2) if lo is not None else None,
            r["pay_src"], _num(r["hours"], int), _num(r["remote"], int), _num(r["external"], int),
            r["published"], r["first_seen"], r["last_seen"], _num(r["detail_ok"], int) or 0,
            r.get("source") or "ba", r.get("url") or "",
        ))
        job_skills += [(r["refnr"], s) for s in r["skills"].split("|") if s]
        job_majors += [(r["refnr"], m) for m in r["majors"].split("|") if m]
    db.executemany(f"INSERT INTO jobs VALUES ({','.join('?' * 24)})", jobs)
    db.executemany("INSERT INTO job_skills VALUES (?, ?)", job_skills)
    db.executemany("INSERT INTO job_majors VALUES (?, ?)", job_majors)
    return db


def query(db, name, **params):
    return [dict(r) for r in db.execute(sql(name), params)]


def ci_too_wide(median, lo, hi):
    return median is None or lo is None or (hi - lo) / median > MAX_CI_REL_WIDTH


def hide_small_medians(rows):
    """Null out medians based on too few roles or employers, or whose 95% confidence
    interval is too wide to say much; keep the sample size visible."""
    for r in rows:
        if ((r.get("with_pay") or 0) < MIN_PAY_SAMPLE or (r.get("pay_employers") or 0) < MIN_PAY_EMPLOYERS
                or ci_too_wide(r["median_pay"], r.get("median_pay_lo"), r.get("median_pay_hi"))):
            r["median_pay"] = r["median_pay_lo"] = r["median_pay_hi"] = None
    return rows


def representative(rows):
    """Groups whose median isn't dominated by a single employer (used for headline claims)."""
    return [r for r in rows if r["median_pay"] and (r.get("top_employer_share") or 1) <= MAX_EMPLOYER_SHARE]


def share(part, whole):
    return round(part / whole, 4) if whole else None


# --- Outputs -----------------------------------------------------------------------

def build_summary(db):
    t = query(db, "totals")[0]
    sources = {r["source"]: r["jobs"] for r in db.execute("SELECT source, COUNT(*) AS jobs FROM active GROUP BY source")}
    totals = {
        **t,
        "by_source": sources,
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
            "note": "Werkstudent postings in Germany from the Bundesagentur's job board and from company "
                    "career sites (via arbeitnow.com); job texts are analysed but not published.",
        },
        "method": {
            "pay": "Hourly pay from the posting's salary fields or its text. Each role (company + title) "
                   "counts once in pay figures, so an employer posting one role in many cities doesn't dominate. "
                   "Medians need at least 10 roles from 5 employers and a 95% confidence interval no wider "
                   "than a quarter of the median (percentile bootstrap, 2000 resamples, fixed seed); headline "
                   "comparisons skip groups where one employer supplies more than 35% of the sample.",
            "no_german": "German is not mentioned in an English posting, is explicitly not required, or is only 'a plus'.",
        },
        "thresholds": {
            "min_pay_sample": MIN_PAY_SAMPLE,
            "min_pay_employers": MIN_PAY_EMPLOYERS,
            "max_employer_share": MAX_EMPLOYER_SHARE,
            "max_ci_rel_width": MAX_CI_REL_WIDTH,
            "bootstrap": {"resamples": stats.BOOTSTRAP_RESAMPLES, "seed": stats.BOOTSTRAP_SEED, "level": stats.CI_LEVEL},
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
    return {**row, "url": row.get("url") or JOB_URL.format(refnr=row["refnr"])}


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


def lifetime_observations(rows, as_of):
    """(entry, exit, event) in days since publication, for Kaplan–Meier with delayed entry.

    A posting enters observation at its first scan (it may have been online for
    months before), is last seen at last_seen, and counts as gone ("event") if it
    wasn't online at the latest scan; it was taken down by the next day.
    """
    out = []
    for r in rows:
        if not r["published"]:
            continue
        pub = date.fromisoformat(r["published"][:10])
        entry = max(0, (date.fromisoformat(r["first_seen"]) - pub).days)
        last = (date.fromisoformat(r["last_seen"]) - pub).days
        gone = r["last_seen"] < as_of
        out.append((entry, last + 1 if gone else last, gone))
    return out


def build_lifetimes(db, as_of):
    """How long Bundesagentur postings stay online, from first/last sightings.

    Only the Bundesagentur's postings: their publication date is reliable, and
    Arbeitnow's are kept a few days after a failed crawl, which blurs when they end.
    """
    rows = [dict(r) for r in db.execute(
        "SELECT category, published, first_seen, last_seen FROM jobs WHERE source = 'ba'")]

    def summary(obs):
        km = stats.kaplan_meier(obs, min_at_risk=MIN_AT_RISK)
        return km, {"postings": len(obs), "gone": sum(1 for o in obs if o[2]),
                    "median_days": km["median"], "observed_until": km["until"]}

    km, overall = summary(lifetime_observations(rows, as_of))
    by_field = {}
    for cat in sorted({r["category"] for r in rows}):
        obs = lifetime_observations([r for r in rows if r["category"] == cat], as_of)
        _, s = summary(obs)
        if s["gone"] < MIN_FIELD_EVENTS:
            s["median_days"] = None
        by_field[cat] = s
    return {
        "as_of": as_of,
        "source": "ba",
        "method": "Kaplan–Meier with delayed entry: age in days since publication; a posting is observed from its "
                  "first scan, counts as gone when missing from the latest scan, and as still online (censored) "
                  f"otherwise. Curves stop where fewer than {MIN_AT_RISK} postings are observed; 95% bands from "
                  "Greenwood's formula (log scale).",
        "min_at_risk": MIN_AT_RISK,
        **overall,
        "curve": {"fields": ["days", "share_online", "lo", "hi", "at_risk"], "rows": km["curve"]},
        "by_field": by_field,
    }


def build_cooccurrence(db, as_of):
    related = defaultdict(list)
    for r in query(db, "cooccurrence", min_pair=COOC_MIN_PAIR, top=COOC_TOP):
        related[r["skill"]].append([r["other"], r["lift"], r["share"], r["together"]])
    return {
        "as_of": as_of,
        "fields": ["skill", "lift", "share", "together"],
        "min_pair": COOC_MIN_PAIR,
        "skills": dict(related),
    }


def build_checker(db, summary):
    """Compact per-posting data for the interactive parts of the site.

    The site filters and aggregates these rows in the browser (by field, city,
    German level and skills), so every chart can react to the filters. Strings
    are replaced by indices into the lists next to them.

    Returns (checker, postings). postings.json holds the display fields for the
    same postings in the same order; it's larger, so the site only loads it
    when the job list is shown.
    """
    skills = [s for s in summary["skills"] if s["jobs"] >= MIN_CHECKER_SKILL_JOBS]
    skill_idx = {s["id"]: i for i, s in enumerate(skills)}
    cats = [c["key"] for c in summary["categories"]]
    cat_idx = {k: i for i, k in enumerate(cats)}
    german_codes = ["none", "plus", "implicit", "required"]
    rows_in = query(db, "checker_jobs")

    # Every place with at least one posting, biggest first, with the median
    # coordinates of its postings (for the map).
    places = defaultdict(list)
    for r in rows_in:
        if r["city"]:
            places[r["city"]].append((r["lat"], r["lon"]))

    def median(values):
        v = sorted(x for x in values if x is not None)
        return v[len(v) // 2] if v else None

    city_list = sorted(places, key=lambda c: (-len(places[c]), c))
    city_idx = {c: i for i, c in enumerate(city_list)}
    cities = [{
        "name": c,
        "lat": median(p[0] for p in places[c]),
        "lon": median(p[1] for p in places[c]),
        "jobs": len(places[c]),
    } for c in city_list]
    # Employers only as numbers: enough to spot a median driven by one company.
    company_idx = {c: i for i, c in enumerate(sorted({r["company"] for r in rows_in}))}

    jobs, rows = [], []
    for r in rows_in:
        ids = sorted(skill_idx[s] for s in (r["skills"] or "").split("|") if s in skill_idx)
        jobs.append([
            cat_idx.get(r["category"], -1),
            city_idx.get(r["city"], -1),
            german_codes.index(r["german"]) if r["german"] in german_codes else 2,
            r["pay"],
            ids,
            int(r["role_first"]),
            int(r["role_city_first"]),
            company_idx[r["company"]],
        ])
        rows.append([r["refnr"], r["title"], r["company"], r["city"], r["published"], r["url"]])
    checker = {
        "as_of": summary["as_of"],
        "fields": ["category", "city", "german", "pay", "skills", "role_first", "role_city_first", "company"],
        "skills": [{"id": s["id"], "label": s["label"], "group": s["group"], "jobs": s["jobs"]} for s in skills],
        "categories": cats,
        "category_labels": {c["key"]: c["label"] for c in summary["categories"]},
        "cities": cities,
        "german": german_codes,
        "min_pay_sample": MIN_PAY_SAMPLE,
        "max_employer_share": MAX_EMPLOYER_SHARE,
        "max_ci_rel_width": MAX_CI_REL_WIDTH,
        "jobs": jobs,
    }
    postings = {
        "as_of": summary["as_of"],
        "url": JOB_URL,
        "fields": ["refnr", "title", "company", "city", "published", "url"],  # url empty: use the template
        "rows": rows,
    }
    return checker, postings


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
            series[f"{name}:median_pay_lo"][i] = _num(r.get("median_pay_lo"))
            series[f"{name}:median_pay_hi"][i] = _num(r.get("median_pay_hi"))
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
    checker, postings = build_checker(db, summary)
    history = build_history(update_history(db, summary["as_of"]))

    rules = patterns.export([s["id"] for s in checker["skills"]])
    outputs = [("summary.json", summary), ("checker.json", checker), ("postings.json", postings),
               ("history.json", history), ("patterns.json", rules),
               ("lifetimes.json", build_lifetimes(db, summary["as_of"])),
               ("cooccurrence.json", build_cooccurrence(db, summary["as_of"]))]
    for name, data in outputs:
        path = write_json(name, data)
        print(f"wrote {os.path.relpath(path, ROOT)} ({os.path.getsize(path) / 1024:.0f} KB)")

    path = og_image.render(summary, os.path.join(OUT_DIR, "og.png"))
    print(f"wrote {os.path.relpath(path, ROOT)} ({os.path.getsize(path) / 1024:.0f} KB)")

    t = summary["totals"]
    print(f"{summary['as_of']}: {t['jobs']} jobs, median {t['median_pay']} €/h (n={t['with_pay']}), "
          f"{t['no_german_share']:.1%} without German, {len(history['dates'])} day(s) of history")


if __name__ == "__main__":
    main()
