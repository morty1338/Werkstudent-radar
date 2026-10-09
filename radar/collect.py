"""Collect all Werkstudent job postings in Germany from the Bundesagentur für Arbeit
job search API and store the raw search results locally.

Usage:
    python -m radar.collect                # writes data/raw/<YYYY-MM-DD>/
    python -m radar.collect --out /tmp/x   # custom output directory

Output (one folder per run date):
    listings.jsonl.gz   one raw API record per line, de-duplicated by referenznummer
    run.json            run metadata: endpoint, per-query totals, counts, duration

Requests are paced and retried (see api.py); the script exits with a non-zero
code and a clear message when the response no longer looks right.
"""

import argparse
import csv
import gzip
import json
import logging
import os
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from . import api
from .extract import is_werkstudent

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(ROOT, "data", "raw")
HISTORY_CSV = os.path.join(ROOT, "data", "history.csv")

# "Werkstudent" also matches "Werkstudentin"/"Werkstudent:in"; the other two
# queries pick up English and gender-neutral titles the first one misses.
QUERIES = ["Werkstudent", "Working Student", "Werkstudierende"]
PAGE_SIZE = 100          # API maximum
REQUEST_DELAY = 0.5      # seconds between pages, to stay polite

# There are ~4,000 Werkstudent postings on any given day. Far fewer means the
# API changed or is filtering us, and the run should fail loudly.
MIN_EXPECTED = 1000
# A real market doesn't halve overnight; a drop like that means a broken query.
MIN_RATIO_VS_LAST_RUN = 0.5

log = logging.getLogger("collect")


class CollectorError(Exception):
    """Raised when the result looks implausible."""


def fetch_query(query):
    """Page through every result for one search term. Returns (total, records)."""
    records, page = [], 1
    while True:
        data = api.search(query, page, PAGE_SIZE)
        total = data["maxErgebnisse"]
        batch = data.get("ergebnisliste") or []
        records.extend(batch)
        log.info("  %-16s page %2d: +%d (%d/%d)", query, page, len(batch), len(records), total)
        if not batch or page * PAGE_SIZE >= total:
            break
        page += 1
        time.sleep(REQUEST_DELAY)
    return total, records


def last_run_total():
    """Active postings on the last day recorded in data/history.csv, if any."""
    if not os.path.exists(HISTORY_CSV):
        return None
    with open(HISTORY_CSV, newline="", encoding="utf-8") as f:
        totals = [r for r in csv.DictReader(f) if r["dim"] == "total"]
    return int(max(totals, key=lambda r: r["date"])["jobs"]) if totals else None


def collect():
    started = time.time()
    by_ref, totals = {}, {}
    for query in QUERIES:
        total, records = fetch_query(query)
        totals[query] = total
        for rec in records:
            ref = rec.get("referenznummer")
            if ref and ref not in by_ref:
                rec["_query"] = query
                by_ref[ref] = rec
        time.sleep(REQUEST_DELAY)

    listings = list(by_ref.values())
    werkstudent = [r for r in listings if is_werkstudent(r.get("stellenangebotsTitel"))]
    meta = {
        "endpoint": api.BASE_URL + api.SEARCH_PATH,
        "queries": totals,
        "unique_postings": len(listings),
        "werkstudent_title": len(werkstudent),
        "duration_s": round(time.time() - started, 1),
    }
    if len(werkstudent) < MIN_EXPECTED:
        raise CollectorError(
            f"only {len(werkstudent)} Werkstudent postings (expected at least {MIN_EXPECTED}); "
            "the API may have changed"
        )
    previous = last_run_total()
    if previous and len(werkstudent) < previous * MIN_RATIO_VS_LAST_RUN:
        raise CollectorError(
            f"only {len(werkstudent)} Werkstudent postings, down from {previous} on the last run; "
            "the API may have changed"
        )
    return listings, meta


def save(listings, meta, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "listings.jsonl.gz")
    with gzip.open(path, "wt", encoding="utf-8") as f:
        for rec in listings:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    with open(os.path.join(out_dir, "run.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", help="output directory (default: data/raw/<today>)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")

    today = datetime.now(ZoneInfo("Europe/Berlin")).date().isoformat()
    out_dir = args.out or os.path.join(RAW_DIR, today)

    try:
        listings, meta = collect()
    except (api.ApiError, CollectorError) as e:
        log.error("collection failed: %s", e)
        return 1

    meta = {"date": today, "collected_at": datetime.now(ZoneInfo("Europe/Berlin")).isoformat(timespec="seconds"), **meta}
    path = save(listings, meta, out_dir)
    log.info("saved %d postings (%d with a Werkstudent title) to %s",
             meta["unique_postings"], meta["werkstudent_title"], os.path.relpath(path, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
