"""Keep the posting history: when each posting was online, day by day.

Usage:
    python -m radar.history              # record today's scan, rebuild data/history.sqlite
    python -m radar.history --backfill   # once: start the history from jobs.csv and history.csv

data/jobs.csv already holds one row per posting ever seen (first_seen,
last_seen, extracted features). What it can't show is the online stretches in
between: a posting that disappears for a few days and comes back, or how many
postings went offline on a given day. This step adds that, in two committed
text tables:

    data/history/scans.csv    date, source, postings   one row per collection day and source
    data/history/online.csv   refnr, start_date, end_date
                              stretches of consecutive scans a posting was online in;
                              end_date is empty while it is still online

Open stretches have no end date, so a line only changes when a posting appears
or disappears, which keeps the daily git diff small. From these and jobs.csv
the step builds data/history.sqlite (git-ignored; schema in
sql/history_schema.sql) and writes docs/data/timeline.json (postings online,
new, back and gone per day).

"Today" is the latest last_seen in jobs.csv, so the step follows radar.enrich.
Running it again for the same day replaces that day's scan.
"""

import argparse
import csv
import json
import logging
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SQL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sql")
JOBS_CSV = os.path.join(ROOT, "data", "jobs.csv")
HISTORY_CSV = os.path.join(ROOT, "data", "history.csv")
HISTORY_DIR = os.path.join(ROOT, "data", "history")
DB_PATH = os.path.join(ROOT, "data", "history.sqlite")
TIMELINE_JSON = os.path.join(ROOT, "docs", "data", "timeline.json")

SCAN_COLUMNS = ["date", "source", "postings"]
ONLINE_COLUMNS = ["refnr", "start_date", "end_date"]
NO_GERMAN = {"none", "plus"}  # same rule as the site's "No German needed"

log = logging.getLogger("history")


def sql(name):
    with open(os.path.join(SQL_DIR, f"{name}.sql"), encoding="utf-8") as f:
        return f.read()


def connect(path=":memory:"):
    if path != ":memory:" and os.path.exists(path):
        os.remove(path)  # always rebuilt from the text tables
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.executescript(sql("history_schema"))
    return db


# --- Text tables <-> database -------------------------------------------------------

def _read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_csv(path, columns, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(columns)
        w.writerows(["" if v is None else v for v in row] for row in rows)


def load_tables(db, history_dir=HISTORY_DIR):
    db.executemany("INSERT INTO scans VALUES (?, ?, ?)",
                   [(r["date"], r["source"], int(r["postings"])) for r in _read_csv(os.path.join(history_dir, "scans.csv"))])
    db.executemany("INSERT INTO online VALUES (?, ?, ?)",
                   [(r["refnr"], r["start_date"], r["end_date"] or None)
                    for r in _read_csv(os.path.join(history_dir, "online.csv"))])


def dump_tables(db, history_dir=HISTORY_DIR):
    """Write the text tables in a stable order, so unchanged rows give no diff."""
    _write_csv(os.path.join(history_dir, "scans.csv"), SCAN_COLUMNS,
               db.execute("SELECT date, source, postings FROM scans ORDER BY date, source"))
    _write_csv(os.path.join(history_dir, "online.csv"), ONLINE_COLUMNS,
               db.execute("SELECT refnr, start_date, end_date FROM online ORDER BY start_date, refnr"))


# --- Postings ---------------------------------------------------------------------------

def read_jobs(path=JOBS_CSV):
    return _read_csv(path)


def _num(s):
    return float(s) if s not in (None, "") else None


def posting_values(r):
    lo, hi = _num(r.get("pay_min")), _num(r.get("pay_max"))
    german = r.get("german") or ""
    return (
        r["refnr"], r.get("source") or "ba", r.get("company") or "", r["first_seen"], r["last_seen"],
        r.get("category") or "", r.get("city") or "", _num(r.get("lat")), _num(r.get("lon")),
        round((lo + hi) / 2, 2) if lo is not None and hi is not None else lo,
        german, (0 if german in NO_GERMAN else 1) if german else None,
    )


def upsert_postings(db, rows):
    """Insert postings or update them in place. first_seen only ever moves back and
    last_seen only forward, so a posting missing from a later scan keeps its last_seen."""
    db.executemany("""
        INSERT INTO postings (refnr, source, company, first_seen, last_seen, field, city, lat, lon,
                              pay, german, german_required)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (refnr) DO UPDATE SET
            source = excluded.source, company = excluded.company,
            first_seen = MIN(postings.first_seen, excluded.first_seen),
            last_seen = MAX(postings.last_seen, excluded.last_seen),
            field = excluded.field, city = excluded.city, lat = excluded.lat, lon = excluded.lon,
            pay = excluded.pay, german = excluded.german, german_required = excluded.german_required
    """, [posting_values(r) for r in rows])
    refs = [(r["refnr"],) for r in rows]
    db.executemany("DELETE FROM posting_skills WHERE refnr = ?", refs)
    db.executemany("INSERT OR IGNORE INTO posting_skills VALUES (?, ?)",
                   [(r["refnr"], s) for r in rows for s in (r.get("skills") or "").split("|") if s])


# --- Scans and online stretches ---------------------------------------------------------

def _previous_scan(db, day):
    return db.execute("SELECT MAX(date) FROM scans WHERE date < ?", (day,)).fetchone()[0]


def _undo_scan(db, day):
    """Take back a scan of `day` so it can be recorded again. Recording `day` closed
    the stretches missing that day at the scan before, and nothing else ends there."""
    prev = _previous_scan(db, day)
    db.execute("DELETE FROM online WHERE start_date = ?", (day,))
    if prev:
        db.execute("UPDATE online SET end_date = NULL WHERE end_date = ?", (prev,))
    db.execute("DELETE FROM scans WHERE date = ?", (day,))


def record_scan(db, day, seen):
    """Record the postings online on `day`. seen: {source: set of refnr}.

    Stretches of postings not seen today end at the previous scan; postings seen
    today without an open stretch start one. Scans must come in date order; the
    latest day may be recorded again.
    """
    latest = db.execute("SELECT MAX(date) FROM scans").fetchone()[0]
    if latest and day < latest:
        raise ValueError(f"scan for {day} is older than the latest scan ({latest})")
    if latest == day:
        _undo_scan(db, day)
    prev = _previous_scan(db, day)
    today = {ref for refs in seen.values() for ref in refs}

    db.execute("CREATE TEMP TABLE IF NOT EXISTS today (refnr TEXT PRIMARY KEY)")
    db.execute("DELETE FROM today")
    db.executemany("INSERT INTO today VALUES (?)", [(r,) for r in today])
    gone = db.execute("UPDATE online SET end_date = ? WHERE end_date IS NULL AND refnr NOT IN (SELECT refnr FROM today)",
                      (prev,)).rowcount
    new = db.execute("""INSERT INTO online (refnr, start_date)
                        SELECT refnr, ? FROM today
                        WHERE refnr NOT IN (SELECT refnr FROM online WHERE end_date IS NULL)""", (day,)).rowcount
    db.executemany("INSERT INTO scans VALUES (?, ?, ?)", [(day, src, len(refs)) for src, refs in sorted(seen.items())])
    return {"online": len(today), "started": new, "ended": gone}


def seen_on(jobs, day):
    seen = {}
    for r in jobs:
        if r["last_seen"] == day:
            seen.setdefault(r.get("source") or "ba", set()).add(r["refnr"])
    return seen


# --- Backfill -------------------------------------------------------------------------------

def backfill(db, jobs, history_rows):
    """Start the history from what was kept before this step existed: one scan per
    day in history.csv, and for each posting one stretch from first_seen to
    last_seen (gaps in between weren't recorded)."""
    days = sorted({r["date"] for r in history_rows} | {r["last_seen"] for r in jobs})
    latest = days[-1]
    for day in days:
        counts = {}
        for r in jobs:
            if r["first_seen"] <= day <= r["last_seen"]:
                src = r.get("source") or "ba"
                counts[src] = counts.get(src, 0) + 1
        db.executemany("INSERT INTO scans VALUES (?, ?, ?)", [(day, s, n) for s, n in sorted(counts.items())])
        recorded = {r["key"]: int(r["jobs"]) for r in history_rows if r["date"] == day and r["dim"] in ("source", "total")}
        if recorded.get("all") not in (None, sum(counts.values())):
            log.warning("%s: %d postings from jobs.csv, %d in history.csv (rows removed from jobs.csv since)",
                        day, sum(counts.values()), recorded["all"])
    db.executemany("INSERT INTO online VALUES (?, ?, ?)",
                   [(r["refnr"], r["first_seen"], None if r["last_seen"] == latest else r["last_seen"]) for r in jobs])


# --- Aggregates for the site -----------------------------------------------------------------

def timeline(db):
    rows = [dict(r) for r in db.execute(sql("history_timeline"))]
    by_source = {}
    dates = [r["date"] for r in rows]
    for r in db.execute("SELECT date, source, postings FROM scans"):
        by_source.setdefault(r["source"], [None] * len(dates))[dates.index(r["date"])] = r["postings"]
    return {
        "as_of": dates[-1] if dates else None,
        "dates": dates,
        "online": [r["online"] for r in rows],
        "new": [r["new"] for r in rows],
        "back": [r["back"] for r in rows],
        "gone": [r["gone"] for r in rows],
        "by_source": dict(sorted(by_source.items())),
    }


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))


# --- Main ----------------------------------------------------------------------------------------

def run(jobs, history_dir=HISTORY_DIR, db_path=DB_PATH, timeline_path=TIMELINE_JSON, backfill_from=None):
    """Record today's scan (or backfill), write the text tables, the database and timeline.json."""
    db = connect(db_path)
    if backfill_from is not None:
        backfill(db, jobs, backfill_from)
        stats = {"backfilled_days": db.execute("SELECT COUNT(DISTINCT date) FROM scans").fetchone()[0]}
    else:
        load_tables(db, history_dir)
        day = max(r["last_seen"] for r in jobs)
        stats = record_scan(db, day, seen_on(jobs, day))
    upsert_postings(db, jobs)
    db.commit()
    dump_tables(db, history_dir)
    data = timeline(db)
    write_json(timeline_path, data)
    db.close()
    return stats, data


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--backfill", action="store_true", help="start the history from jobs.csv and history.csv")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")

    jobs = read_jobs()
    if args.backfill and _read_csv(os.path.join(HISTORY_DIR, "scans.csv")):
        log.error("%s already has scans; remove it first to backfill again", os.path.relpath(HISTORY_DIR, ROOT))
        return 1
    stats, data = run(jobs, backfill_from=_read_csv(HISTORY_CSV) if args.backfill else None)
    log.info("%s: %s; %d scan day(s); wrote %s, %s and %s", data["as_of"], stats, len(data["dates"]),
             os.path.relpath(HISTORY_DIR, ROOT), os.path.relpath(DB_PATH, ROOT), os.path.relpath(TIMELINE_JSON, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
