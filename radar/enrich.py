"""Turn the latest raw listings into data/jobs.csv: one row per Werkstudent
posting ever seen, with features extracted from its description.

Usage:
    python -m radar.enrich                # use the newest data/raw/<date>/
    python -m radar.enrich --date 2026-10-09
    python -m radar.enrich --retag        # re-run extraction on all active jobs (from the local cache)

Only postings that are new, failed before, or were tagged by an older
extractor version get their full text fetched. Texts are cached locally in
data/raw/<date>/details.jsonl.gz (git-ignored) and never written to jobs.csv:
the descriptions belong to the employers, only derived features are kept.
"""

import argparse
import csv
import glob
import gzip
import json
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import api
from .extract import EXTRACTOR_VERSION, extract, is_werkstudent

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(ROOT, "data", "raw")
JOBS_CSV = os.path.join(ROOT, "data", "jobs.csv")

FIELDS = [
    "refnr", "title", "company", "city", "region", "category", "hauptberuf",
    "lang", "german", "english", "pay_min", "pay_max", "pay_src", "hours",
    "skills", "majors", "remote", "external", "published",
    "first_seen", "last_seen", "detail_ok", "xv",
]
# Detail fields kept in the local cache: the text plus the salary fields,
# which are sometimes only filled in the detail record.
CACHED_DETAIL_FIELDS = [
    "referenznummer", "stellenangebotsBeschreibung", "verguetungsangabe",
    "artDerVerguetung", "festgehalt", "gehaltsspanneVon", "gehaltsspanneBis",
]
WORKERS = 4
MAX_MISSING_TEXT = 0.5   # fail the run if more than half the fetched postings have no text

log = logging.getLogger("enrich")


def latest_raw_dir():
    dirs = sorted(d for d in glob.glob(os.path.join(RAW_DIR, "*")) if os.path.isfile(os.path.join(d, "listings.jsonl.gz")))
    if not dirs:
        sys.exit("no raw data found; run `python -m radar.collect` first")
    return dirs[-1]


def read_jsonl_gz(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_listings(raw_dir):
    listings = read_jsonl_gz(os.path.join(raw_dir, "listings.jsonl.gz"))
    return {r["referenznummer"]: r for r in listings if is_werkstudent(r.get("stellenangebotsTitel"))}


def load_detail_cache():
    cache = {}
    for path in sorted(glob.glob(os.path.join(RAW_DIR, "*", "details.jsonl.gz"))):
        for rec in read_jsonl_gz(path):
            cache[rec["referenznummer"]] = rec
    return cache


def load_jobs():
    if not os.path.exists(JOBS_CSV):
        return {}
    with open(JOBS_CSV, newline="", encoding="utf-8") as f:
        return {r["refnr"]: r for r in csv.DictReader(f)}


def save_jobs(jobs):
    rows = sorted(jobs.values(), key=lambda r: (r["first_seen"], r["refnr"]))
    tmp = JOBS_CSV + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp, JOBS_CSV)


def fetch_details(refs, cache_path, workers):
    """Fetch full postings in parallel and append them to the local cache.

    Returns (details, errors): refnr -> trimmed record (None if the posting is
    gone), and the number of requests that failed outright.
    """
    details, errors = {}, 0
    started = time.time()
    with ThreadPoolExecutor(max_workers=workers) as pool, gzip.open(cache_path, "at", encoding="utf-8") as cache:
        futures = {pool.submit(api.job_details, ref): ref for ref in refs}
        for i, fut in enumerate(as_completed(futures), 1):
            ref = futures[fut]
            try:
                rec = fut.result()
            except api.ApiError as e:
                log.warning("details for %s failed: %s", ref, e)
                rec, errors = None, errors + 1
            if rec:
                rec = {k: rec.get(k) for k in CACHED_DETAIL_FIELDS}
                cache.write(json.dumps(rec, ensure_ascii=False) + "\n")
            details[ref] = rec
            if i % 500 == 0 or i == len(refs):
                log.info("  details %d/%d (%.0fs)", i, len(refs), time.time() - started)
    return details, errors


def needs_tagging(row, retag):
    return (
        row is None
        or retag
        or row.get("detail_ok") != "1"
        or int(row.get("xv") or 0) < EXTRACTOR_VERSION
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--date", help="raw data folder to use (default: newest)")
    parser.add_argument("--retag", action="store_true", help="re-run extraction on every active job")
    parser.add_argument("--offline", action="store_true", help="only use cached texts, never call the API")
    parser.add_argument("--workers", type=int, default=WORKERS)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")

    raw_dir = os.path.join(RAW_DIR, args.date) if args.date else latest_raw_dir()
    day = os.path.basename(raw_dir)
    listings = load_listings(raw_dir)
    jobs = load_jobs()
    cache = load_detail_cache()
    log.info("%s: %d Werkstudent postings, %d known jobs, %d cached texts", day, len(listings), len(jobs), len(cache))

    to_tag = [ref for ref in listings if needs_tagging(jobs.get(ref), args.retag)]
    to_fetch = [ref for ref in to_tag if ref not in cache]
    fetched, errors, missing_text = {}, 0, 0
    if to_fetch and not args.offline:
        log.info("fetching %d job descriptions…", len(to_fetch))
        fetched, errors = fetch_details(to_fetch, os.path.join(raw_dir, "details.jsonl.gz"), args.workers)
        cache.update({ref: rec for ref, rec in fetched.items() if rec})
        missing_text = sum(1 for rec in fetched.values() if not (rec and rec.get("stellenangebotsBeschreibung")))

    for ref, listing in listings.items():
        row = jobs.get(ref)
        if ref in to_tag:
            features = extract(listing, cache.get(ref))
            if row and row.get("detail_ok") == "1" and not features["detail_ok"]:
                features = {}  # text unavailable today: keep yesterday's tags instead of blanking them
            row = {**(row or {}), **features}
        row.update({
            "refnr": ref,
            "title": (listing.get("stellenangebotsTitel") or "").strip(),
            "company": (listing.get("firma") or "").strip(),
            "hauptberuf": listing.get("hauptberuf") or "",
            "external": int(bool(listing.get("externeURL"))),
            "published": listing.get("datumErsteVeroeffentlichung") or "",
            "first_seen": row.get("first_seen") or day,
            "last_seen": day,
        })
        jobs[ref] = row

    save_jobs(jobs)
    tagged = sum(1 for ref in listings if str(jobs[ref].get("detail_ok")) == "1")
    log.info("wrote %s: %d jobs total, %d active on %s, %d of them with extracted features",
             os.path.relpath(JOBS_CSV, ROOT), len(jobs), len(listings), day, tagged)

    if fetched and missing_text / len(fetched) > MAX_MISSING_TEXT:
        log.error("%d of %d fetched postings came back without text (%d request errors); "
                  "the details endpoint %s may have changed", missing_text, len(fetched), errors, api.DETAIL_PATH)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
