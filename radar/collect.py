"""Collect all Werkstudent job postings in Germany from the Bundesagentur für Arbeit
job search API and store the raw search results locally.

Usage:
    python -m radar.collect                # writes data/raw/<YYYY-MM-DD>/
    python -m radar.collect --out /tmp/x   # custom output directory

Output (one folder per run date):
    listings.jsonl.gz   one raw API record per line, de-duplicated by referenznummer
    run.json            run metadata: endpoint, per-query totals, counts, duration

The API is unofficial and changes without notice, so every request is retried
with backoff, requests are paced, and the script exits with a non-zero code and
a clear message when the response no longer looks right.
"""

import argparse
import gzip
import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(ROOT, "data", "raw")

BASE_URL = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service"
SEARCH_PATH = "/pc/v6/jobs"
HEADERS = {
    # Public client id used by the arbeitsagentur.de web app; not a secret.
    "X-API-Key": "jobboerse-jobsuche",
    "User-Agent": "werkstudent-radar/0.1 (+https://github.com/morty1338/werkstudent-radar)",
    "Accept": "application/json",
}

# "Werkstudent" also matches "Werkstudentin"/"Werkstudent:in"; the other two
# queries pick up English and gender-neutral titles the first one misses.
QUERIES = ["Werkstudent", "Working Student", "Werkstudierende"]
PAGE_SIZE = 100          # API maximum
REQUEST_DELAY = 0.5      # seconds between pages, to stay polite
RETRIES = 4
TIMEOUT = 30

# There are ~4,000 Werkstudent postings on any given day. Far fewer means the
# API changed or is filtering us, and the run should fail loudly.
MIN_EXPECTED = 1000

WERKSTUDENT_TITLE = re.compile(r"werk-?stud|working[- ]student", re.IGNORECASE)

log = logging.getLogger("collect")


class CollectorError(Exception):
    """Raised when the API answers in a way we can't trust."""


def get_json(session, url, params):
    """GET with retries and exponential backoff on network errors, 429 and 5xx."""
    last_error = None
    for attempt in range(1, RETRIES + 1):
        try:
            resp = session.get(url, params=params, timeout=TIMEOUT)
        except requests.RequestException as e:
            last_error = f"network error: {e}"
        else:
            if resp.status_code == 200:
                try:
                    return resp.json()
                except ValueError:
                    last_error = "response is not JSON"
            elif resp.status_code == 429 or resp.status_code >= 500:
                last_error = f"HTTP {resp.status_code}"
            else:
                # 4xx other than 429 won't fix itself (e.g. 403 when an API version is retired).
                raise CollectorError(f"HTTP {resp.status_code} from {resp.url}: {resp.text[:200]}")
        wait = 2 ** attempt
        log.warning("attempt %d/%d failed (%s), retrying in %ds", attempt, RETRIES, last_error, wait)
        time.sleep(wait)
    raise CollectorError(f"giving up on {url} {params}: {last_error}")


def fetch_query(session, query):
    """Page through every result for one search term. Returns (total, records)."""
    url = BASE_URL + SEARCH_PATH
    records, page, total = [], 1, None
    while True:
        data = get_json(session, url, {"was": query, "page": page, "size": PAGE_SIZE})
        if not isinstance(data, dict) or "maxErgebnisse" not in data:
            raise CollectorError(f"unexpected response shape for '{query}' page {page}: keys={list(data)[:10]}")
        total = data["maxErgebnisse"]
        batch = data.get("ergebnisliste") or []
        records.extend(batch)
        log.info("  %-16s page %2d: +%d (%d/%d)", query, page, len(batch), len(records), total)
        if not batch or page * PAGE_SIZE >= total:
            break
        page += 1
        time.sleep(REQUEST_DELAY)
    return total, records


def collect():
    started = time.time()
    session = requests.Session()
    session.headers.update(HEADERS)

    by_ref, totals = {}, {}
    for query in QUERIES:
        total, records = fetch_query(session, query)
        totals[query] = total
        for rec in records:
            ref = rec.get("referenznummer")
            if ref and ref not in by_ref:
                rec["_query"] = query
                by_ref[ref] = rec
        time.sleep(REQUEST_DELAY)

    listings = list(by_ref.values())
    werkstudent = [r for r in listings if WERKSTUDENT_TITLE.search(r.get("stellenangebotsTitel") or "")]
    meta = {
        "endpoint": BASE_URL + SEARCH_PATH,
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
    except CollectorError as e:
        log.error("collection failed: %s", e)
        return 1

    meta = {"date": today, "collected_at": datetime.now(ZoneInfo("Europe/Berlin")).isoformat(timespec="seconds"), **meta}
    path = save(listings, meta, out_dir)
    log.info("saved %d postings (%d with a Werkstudent title) to %s",
             meta["unique_postings"], meta["werkstudent_title"], os.path.relpath(path, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
