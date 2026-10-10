"""Turn the latest raw listings into data/jobs.csv: one row per Werkstudent
posting ever seen, with features extracted from its description.

Usage:
    python -m radar.enrich                # use the newest data/raw/<date>/
    python -m radar.enrich --date 2026-10-09
    python -m radar.enrich --retag        # re-run extraction on all active jobs (from the local cache)

Postings come from two sources: the Bundesagentur's job board (data/raw/<date>/
listings.jsonl.gz, texts fetched per posting) and company career sites via
Arbeitnow (arbeitnow.jsonl.gz, texts included; see radar/arbeitnow.py).
Arbeitnow postings that the Bundesagentur also has are skipped.

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

import re
from datetime import date, timedelta

from . import api, arbeitnow
from .extract import EXTRACTOR_VERSION, extract, is_werkstudent

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(ROOT, "data", "raw")
JOBS_CSV = os.path.join(ROOT, "data", "jobs.csv")

FIELDS = [
    "refnr", "title", "company", "city", "region", "lat", "lon", "category", "hauptberuf",
    "lang", "german", "english", "pay_min", "pay_max", "pay_src", "hours",
    "skills", "majors", "remote", "external", "published",
    "first_seen", "last_seen", "detail_ok", "xv", "source", "url",
]
# Detail fields kept in the local cache: the text plus the salary fields,
# which are sometimes only filled in the detail record.
CACHED_DETAIL_FIELDS = [
    "referenznummer", "stellenangebotsBeschreibung", "verguetungsangabe",
    "artDerVerguetung", "festgehalt", "gehaltsspanneVon", "gehaltsspanneBis",
]
WORKERS = 4
MAX_MISSING_TEXT = 0.5   # fail the run if more than half the fetched postings have no text
CARRY_FORWARD_DAYS = 3   # keep recently seen Arbeitnow postings when its crawl was incomplete

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


# --- Second source: company career sites via Arbeitnow ------------------------------------

def same_posting_key(company, title):
    """Company + title, normalised, to spot the same posting on both sources."""
    norm = lambda s: re.sub(r"[^a-z0-9]", "", re.sub(r"\(.*?\)", "", (s or "").lower()))
    return norm(company)[:12], norm(title)[:40]


def load_arbeitnow(raw_dir):
    """Postings of the day and whether the crawl finished (None if it didn't run)."""
    path = os.path.join(raw_dir, "arbeitnow.jsonl.gz")
    if not os.path.exists(path):
        return [], None
    meta_path = os.path.join(raw_dir, "arbeitnow.json")
    complete = json.load(open(meta_path)).get("complete", False) if os.path.exists(meta_path) else False
    return read_jsonl_gz(path), complete


def merge_arbeitnow(jobs, day, an_jobs, complete, ba_keys, places, retag=False):
    """Add or update Arbeitnow postings in jobs; returns counts for the log.

    ba_keys: same_posting_key()s of today's Bundesagentur postings (those win).
    places: {city: (lat, lon)} of German places known from the Bundesagentur data.
    """
    stats = {"kept": 0, "not_werkstudent": 0, "duplicates": 0, "abroad": 0, "carried": 0}
    seen = set()
    for job in an_jobs:
        if not arbeitnow.is_werkstudent_job(job):  # the rule may have changed since the crawl
            stats["not_werkstudent"] += 1
            continue
        key = same_posting_key(job.get("company_name"), job.get("title"))
        if key in ba_keys:
            stats["duplicates"] += 1
            continue
        city, remote, in_germany = arbeitnow.place(job.get("location"), places)
        if not in_germany:
            stats["abroad"] += 1
            continue
        ref = arbeitnow.ref(job)
        seen.add(ref)
        row = jobs.get(ref)
        text = arbeitnow.html_to_text(job.get("description"))
        if needs_tagging(row, retag):
            listing = {
                "stellenangebotsTitel": job.get("title") or "",
                "hauptberuf": "",
                "homeofficemoeglich": remote or bool(job.get("remote")),
                "stellenlokationen": [{"adresse": {"ort": city}}],
            }
            row = {**(row or {}), **extract(listing, {"stellenangebotsBeschreibung": text})}
        lat, lon = places.get(city, ("", ""))
        row.update({
            "refnr": ref,
            "title": (job.get("title") or "").strip(),
            "company": (job.get("company_name") or "").strip(),
            "city": city,
            "region": "",
            "lat": lat,
            "lon": lon,
            "hauptberuf": "",
            "external": 1,
            "published": arbeitnow.published(job),
            "first_seen": row.get("first_seen") or day,
            "last_seen": day,
            "source": "arbeitnow",
            "url": job.get("url") or "",
        })
        jobs[ref] = row
        stats["kept"] += 1

    if not complete:
        # The crawl stopped early (or didn't run): postings it didn't reach are
        # probably still online, so keep the recently seen ones for today.
        cutoff = (date.fromisoformat(day) - timedelta(days=CARRY_FORWARD_DAYS)).isoformat()
        for ref, row in jobs.items():
            if row.get("source") == "arbeitnow" and ref not in seen and cutoff <= row["last_seen"] < day:
                row["last_seen"] = day
                stats["carried"] += 1
    return stats


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
        loc = (listing.get("stellenlokationen") or [{}])[0]
        row.update({
            "refnr": ref,
            "lat": round(loc["breite"], 4) if loc.get("breite") is not None else "",
            "lon": round(loc["laenge"], 4) if loc.get("laenge") is not None else "",
            "title": (listing.get("stellenangebotsTitel") or "").strip(),
            "company": (listing.get("firma") or "").strip(),
            "hauptberuf": listing.get("hauptberuf") or "",
            "external": int(bool(listing.get("externeURL"))),
            "published": listing.get("datumErsteVeroeffentlichung") or "",
            "first_seen": row.get("first_seen") or day,
            "last_seen": day,
            "source": "ba",
            "url": "",
        })
        jobs[ref] = row

    # Company career sites (Arbeitnow). German places and their coordinates come
    # from the Bundesagentur's postings.
    an_jobs, complete = load_arbeitnow(raw_dir)
    places = {}
    for row in jobs.values():
        if row.get("source", "ba") != "arbeitnow" and row.get("city") and row.get("lat") not in ("", None):
            places.setdefault(row["city"], (row["lat"], row["lon"]))
    ba_keys = {same_posting_key(jobs[r]["company"], jobs[r]["title"]) for r in listings}
    stats = merge_arbeitnow(jobs, day, an_jobs, complete, ba_keys, places, args.retag)
    log.info("arbeitnow: %s (%s)", stats, "no crawl today" if complete is None else "complete" if complete else "INCOMPLETE crawl")

    save_jobs(jobs)
    active = [r for r in jobs.values() if r["last_seen"] == day]
    tagged = sum(1 for r in active if str(r.get("detail_ok")) == "1")
    log.info("wrote %s: %d jobs total, %d active on %s (%d from company career sites), %d with extracted features",
             os.path.relpath(JOBS_CSV, ROOT), len(jobs), len(active), day,
             sum(r.get("source") == "arbeitnow" for r in active), tagged)

    if fetched and missing_text / len(fetched) > MAX_MISSING_TEXT:
        log.error("%d of %d fetched postings came back without text (%d request errors); "
                  "the details endpoint %s may have changed", missing_text, len(fetched), errors, api.DETAIL_PATH)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
