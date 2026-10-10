"""Data-quality checks for the daily run. A failed check fails the run.

Usage:
    python -m radar.checks

Runs after radar.history (it needs today's scan) and before anything is
committed, so bad data never reaches the site. A failed run opens the
"Daily data update failed" issue, which GitHub sends by e-mail.

    volume   postings online today per source vs. the median of the previous
             (up to) 7 scans: more than 50% fewer or more fails for the
             Bundesagentur; for Arbeitnow, an optional source with its own
             fallback, it only warns
    fields   today's raw Bundesagentur listings: every one has a reference
             number; title, employer, place and publication date are missing in
             at most 2% (a renamed API field shows up here first)
    pay      every hourly rate of today's postings lies within 12–60 €/h and
             pay_min ≤ pay_max

The results are printed and, in GitHub Actions, added to the run summary.
"""

import csv
import gzip
import json
import logging
import os
import statistics
import sys
from dataclasses import dataclass

from .extract import PAY_MAX, PAY_MIN

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOBS_CSV = os.path.join(ROOT, "data", "jobs.csv")
SCANS_CSV = os.path.join(ROOT, "data", "history", "scans.csv")
RAW_DIR = os.path.join(ROOT, "data", "raw")

VOLUME_WINDOW = 7          # previous scans the median is taken over
MAX_VOLUME_CHANGE = 0.5    # ±50% vs. that median
MAX_MISSING_SHARE = 0.02   # optional-but-expected listing fields
STRICT_SOURCES = {"ba"}    # sources whose volume check fails the run (others warn)
LISTING_KEY = "referenznummer"
LISTING_FIELDS = {
    "stellenangebotsTitel": "title",
    "firma": "employer",
    "stellenlokationen": "place",
    "datumErsteVeroeffentlichung": "publication date",
}

log = logging.getLogger("checks")


@dataclass
class Result:
    check: str
    status: str   # ok | warn | fail
    detail: str


def _read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def check_volume(scans, day):
    """scans: rows of data/history/scans.csv (date, source, postings)."""
    results = []
    for source in sorted({r["source"] for r in scans if r["date"] == day}):
        today = next(int(r["postings"]) for r in scans if r["date"] == day and r["source"] == source)
        before = sorted((r for r in scans if r["source"] == source and r["date"] < day), key=lambda r: r["date"])
        before = [int(r["postings"]) for r in before[-VOLUME_WINDOW:]]
        name = f"volume:{source}"
        if not before:
            results.append(Result(name, "ok", f"{today} postings (first scan of this source, nothing to compare)"))
            continue
        median = statistics.median(before)
        change = today / median - 1 if median else float("inf")
        detail = f"{today} postings vs. median {median:g} of the last {len(before)} scan(s) ({change:+.0%})"
        if abs(change) <= MAX_VOLUME_CHANGE:
            results.append(Result(name, "ok", detail))
        else:
            results.append(Result(name, "fail" if source in STRICT_SOURCES else "warn", detail))
    if not results:
        results.append(Result("volume", "fail", f"no scan recorded for {day}"))
    return results


def check_fields(listings):
    """listings: raw Bundesagentur search results of today."""
    if not listings:
        return [Result("fields", "fail", "no raw listings")]
    n = len(listings)
    no_key = sum(1 for r in listings if not r.get(LISTING_KEY))
    if no_key:
        return [Result("fields", "fail", f"{no_key} of {n} listings have no {LISTING_KEY}")]
    missing = {label: sum(1 for r in listings if not r.get(key)) for key, label in LISTING_FIELDS.items()}
    bad = {label: k for label, k in missing.items() if k / n > MAX_MISSING_SHARE}
    if bad:
        return [Result("fields", "fail", "missing in more than 2% of listings: "
                       + ", ".join(f"{label} ({k} of {n})" for label, k in bad.items()))]
    worst = max(missing.items(), key=lambda kv: kv[1])
    return [Result("fields", "ok", f"{n} listings; most often missing: {worst[0]} ({worst[1]})")]


def check_pay(jobs, day):
    """jobs: rows of data/jobs.csv; checks the postings online on `day`."""
    bad, n = [], 0
    for r in jobs:
        if r["last_seen"] != day or r["pay_min"] in ("", None):
            continue
        n += 1
        lo, hi = float(r["pay_min"]), float(r["pay_max"] or r["pay_min"])
        if not (PAY_MIN <= lo <= hi <= PAY_MAX):
            bad.append(f"{r['refnr']} ({lo:g}–{hi:g} €/h)")
    if bad:
        return [Result("pay", "fail", f"{len(bad)} of {n} rates outside {PAY_MIN:g}–{PAY_MAX:g} €/h: " + ", ".join(bad[:5]))]
    return [Result("pay", "ok", f"{n} rates, all within {PAY_MIN:g}–{PAY_MAX:g} €/h")]


def read_listings(day, raw_dir=RAW_DIR):
    path = os.path.join(raw_dir, day, "listings.jsonl.gz")
    if not os.path.exists(path):
        return []
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def run_checks(jobs, scans, listings):
    day = max(r["last_seen"] for r in jobs)
    return day, check_volume(scans, day) + check_fields(listings) + check_pay(jobs, day)


def report(day, results):
    icon = {"ok": "✅", "warn": "⚠️", "fail": "❌"}
    lines = [f"### Data checks for {day}", "", "| Check | Result | Detail |", "|---|---|---|"]
    lines += [f"| {r.check} | {icon[r.status]} {r.status} | {r.detail} |" for r in results]
    return "\n".join(lines) + "\n"


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    jobs = _read_csv(JOBS_CSV)
    day = max(r["last_seen"] for r in jobs)
    day, results = run_checks(jobs, _read_csv(SCANS_CSV), read_listings(day))
    for r in results:
        {"ok": log.info, "warn": log.warning, "fail": log.error}[r.status]("%-15s %-4s %s", r.check, r.status, r.detail)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(report(day, results))
    failed = [r for r in results if r.status == "fail"]
    if failed:
        log.error("%d data check(s) failed; nothing is committed today", len(failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
