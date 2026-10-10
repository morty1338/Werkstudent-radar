"""Second source: Werkstudent postings from company career sites, via the free
Arbeitnow job board API (https://www.arbeitnow.com/api/job-board-api).

Arbeitnow collects postings from companies' own applicant tracking systems
(Personio, Greenhouse, Lever, …), which is where LinkedIn and other boards copy
them from too. It covers many start-ups that never post on the Bundesagentur's
board. Its terms: free public API, "please do not abuse", a link back is
appreciated (the site links to it).

Usage:
    python -m radar.arbeitnow     # writes data/raw/<date>/arbeitnow.jsonl.gz and arbeitnow.json

The whole board is paged through once a day, slowly (the API answers
"429 Too Many Requests" to fast clients). If it stops early, the run is marked
incomplete and enrich keeps recently seen postings instead of dropping them.
"""

import argparse
import gzip
import html
import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

from .extract import is_werkstudent, normalise_city

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(ROOT, "data", "raw")
API = "https://www.arbeitnow.com/api/job-board-api"
HEADERS = {"User-Agent": "werkstudent-radar/0.1 (+https://github.com/morty1338/werkstudent-radar)", "Accept": "application/json"}
PAGE_DELAY = 5          # seconds between pages
RATE_LIMIT_WAIT = 90    # seconds to wait after a 429
RETRIES = 3
MAX_PAGES = 400
REFNR_PREFIX = "an:"

log = logging.getLogger("arbeitnow")

_STUDENT_TYPE = re.compile(r"werk-?stud|working[- ]student", re.IGNORECASE)
# Other student contracts that Arbeitnow sometimes also types as "Working student".
_OTHER_CONTRACT = re.compile(
    r"abschlussarbeit|masterarbeit|bachelorarbeit|thesis|projektarbeit|praktik|\bintern\b|internship|hilfskraft|minijob|aushilfe",
    re.IGNORECASE,
)


def is_werkstudent_job(job):
    """Werkstudent in the title, or typed as one by the employer and not another kind of student job."""
    if is_werkstudent(job.get("title")):
        return True
    typed = any(_STUDENT_TYPE.search(t or "") for t in job.get("job_types") or [])
    return typed and not _OTHER_CONTRACT.search(job.get("title") or "")


def html_to_text(markup):
    """Job descriptions come as HTML; keep line breaks so list items stay separate."""
    text = re.sub(r"(?i)<br\s*/?>|</(?:p|div|li|h\d|tr)>", "\n", markup or "")
    text = re.sub(r"(?i)<li[^>]*>", "\n• ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    lines = (re.sub(r"[ \t ]+", " ", line).strip() for line in text.split("\n"))
    return "\n".join(line for line in lines if line)


# --- Location ---------------------------------------------------------------------------

_REMOTE = re.compile(r"\b(remote|home\s?office|homeoffice|mobiles? arbeiten|deutschlandweit|bundesweit)\b", re.IGNORECASE)
_GERMANY = re.compile(
    r"\b(germany|deutschland|bayern|bavaria|baden-w(?:ü|ue)rttemberg|nrw|nordrhein-westfalen|hessen|hesse|niedersachsen"
    r"|lower saxony|sachsen|saxony|th(?:ü|ue)ringen|brandenburg|schleswig-holstein|rheinland-pfalz|saarland)\b",
    re.IGNORECASE,
)
# Explicit signs of another country. Anything else is taken as German: a
# Werkstudent contract only exists in Germany.
_ABROAD = re.compile(
    r"\b(switzerland|schweiz|suisse|z(?:ü|u)rich|zurich|basel|bern|geneva|genf|lausanne|zug|austria|(?:ö|oe)sterreich|wien|vienna"
    r"|graz|linz|salzburg|innsbruck|united kingdom|uk|england|london|manchester|france|paris|lyon|spain|espa(?:ñ|n)a|madrid"
    r"|barcelona|netherlands|nederland|amsterdam|rotterdam|belgium|brussels|luxembourg|poland|polska|warsaw|warszawa|krak(?:ó|o)w"
    r"|portugal|lisbon|lisboa|italy|italia|milan|milano|rome|denmark|copenhagen|sweden|stockholm|norway|oslo|finland|helsinki"
    r"|ireland|dublin|czech|prague|praha|usa|united states|new york|canada|toronto|india|bangalore|singapore|dubai)\b",
    re.IGNORECASE,
)
_ENGLISH_NAMES = {"Hanover": "Hannover", "Dusseldorf": "Düsseldorf", "Duesseldorf": "Düsseldorf", "Cologne": "Köln",
                  "Munich": "München", "Nuremberg": "Nürnberg", "Brunswick": "Braunschweig"}


def _clean(part):
    part = re.sub(r"\s+(office|hq|headquarters|zentrale|filiale|standort)$", "", part.strip(), flags=re.IGNORECASE)
    return _ENGLISH_NAMES.get(part, normalise_city(part))


def place(location, german_cities):
    """Return (city, remote, in_germany) for Arbeitnow's free-text location.

    german_cities: city names known from the Bundesagentur data. Locations come
    in many shapes: "Berlin (Zentrale)", "Gräfelfing/Munich", "Cybay Hannover",
    "Berlin oder Mainz", "Remote".
    """
    loc = (location or "").strip()
    remote = bool(_REMOTE.search(loc))
    if _ABROAD.search(loc) and not _GERMANY.search(loc) and not any(
        _clean(p) in german_cities for p in re.split(r"[,/|;]| oder | or ", loc)
    ):
        return "", remote, False
    parts = [p for p in re.split(r"[,/|;()]| oder | or | - ", loc) if p.strip()]
    # A known German city in any part, or as a word inside a part ("Cybay Hannover").
    for part in parts:
        city = _clean(part)
        if city in german_cities:
            return city, remote, True
        for word in re.findall(r"[A-ZÄÖÜ][\wäöüß.-]+", part):
            if _clean(word) in german_cities:
                return _clean(word), remote, True
    if remote or not parts:
        return "", True, True
    first = _clean(parts[0])
    # An unknown place (a small town the Bundesagentur data hasn't seen yet).
    return ("" if _GERMANY.fullmatch(first) else first), remote, True


def ref(job):
    return REFNR_PREFIX + job["slug"]


def published(job):
    ts = job.get("created_at")
    return datetime.fromtimestamp(ts, ZoneInfo("Europe/Berlin")).date().isoformat() if ts else ""


# --- Fetching -----------------------------------------------------------------------------

def get_page(session, page):
    for attempt in range(1, RETRIES + 1):
        try:
            r = session.get(API, params={"page": page}, timeout=30)
        except requests.RequestException as e:
            log.warning("page %d: %s (attempt %d)", page, e, attempt)
            time.sleep(10 * attempt)
            continue
        if r.status_code == 200:
            return r.json()
        if r.status_code == 429:
            log.warning("page %d: rate limited, waiting %ds", page, RATE_LIMIT_WAIT)
            time.sleep(RATE_LIMIT_WAIT)
            continue
        log.warning("page %d: HTTP %d (attempt %d)", page, r.status_code, attempt)
        time.sleep(10 * attempt)
    return None


def fetch(out_dir):
    session = requests.Session()
    session.headers.update(HEADERS)
    kept, seen, page, complete = {}, 0, 1, False
    started = time.time()
    while page <= MAX_PAGES:
        data = get_page(session, page)
        if not data or not isinstance(data.get("data"), list):
            log.error("stopped at page %d: no usable answer", page)
            break
        for job in data["data"]:
            seen += 1
            if job.get("slug") and is_werkstudent_job(job):
                kept[job["slug"]] = job
        if not data["data"] or not (data.get("links") or {}).get("next"):
            complete = True
            break
        if page % 10 == 0:
            log.info("  page %d: %d postings seen, %d Werkstudent", page, seen, len(kept))
        page += 1
        time.sleep(PAGE_DELAY)

    os.makedirs(out_dir, exist_ok=True)
    with gzip.open(os.path.join(out_dir, "arbeitnow.jsonl.gz"), "wt", encoding="utf-8") as f:
        for job in kept.values():
            f.write(json.dumps(job, ensure_ascii=False) + "\n")
    meta = {
        "complete": complete,
        "pages": page,
        "postings_seen": seen,
        "werkstudent": len(kept),
        "duration_s": round(time.time() - started, 1),
        "finished_at": datetime.now(ZoneInfo("Europe/Berlin")).isoformat(timespec="seconds"),
    }
    with open(os.path.join(out_dir, "arbeitnow.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    return meta


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", help="output directory (default: data/raw/<today>)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    today = datetime.now(ZoneInfo("Europe/Berlin")).date().isoformat()
    meta = fetch(args.out or os.path.join(RAW_DIR, today))
    log.info("arbeitnow: %d Werkstudent postings out of %d (%s, %d pages)",
             meta["werkstudent"], meta["postings_seen"], "complete" if meta["complete"] else "INCOMPLETE", meta["pages"])
    return 0 if meta["postings_seen"] else 1


if __name__ == "__main__":
    sys.exit(main())
