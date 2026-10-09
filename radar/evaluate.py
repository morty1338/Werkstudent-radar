"""Measure how well the extraction rules work against hand-labelled postings.

    python -m radar.evaluate sample   # draw the sample, write data/eval/sample.json (local only)
    python -m radar.evaluate label    # labelling form on http://localhost:8766, saves data/eval/labels.csv
    python -m radar.evaluate report   # compare rules vs. labels, write data/eval/report.md

The sample has three strata, shuffled together so the labeller can't tell them apart:

    random     70 postings drawn at random   -> overall accuracy of every rule
    no_german  20 postings the rules call "open without German" -> precision of the headline claim
    pay_text   10 postings whose pay was found in the text -> precision of text pay extraction

Labelling is blind: the form shows the posting text but none of the predictions.
sample.json holds the job texts and stays git-ignored; labels.csv holds only
reference numbers and the labeller's answers, so it can be committed.
"""

import argparse
import csv
import json
import os
import random
from collections import Counter
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from .enrich import JOBS_CSV, load_detail_cache
from .extract import CATEGORIES, EXTRACTOR_VERSION, extract

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVAL_DIR = os.path.join(ROOT, "data", "eval")
SAMPLE_JSON = os.path.join(EVAL_DIR, "sample.json")
SAMPLE_IDS = os.path.join(EVAL_DIR, "sample_ids.csv")
LABELS_CSV = os.path.join(EVAL_DIR, "labels.csv")
LABEL_FIELDS = ["refnr", "is_werkstudent", "category", "german", "pay_min", "pay_max", "skills", "note"]
LABEL_PORT = 8766
REPORT_MD = os.path.join(EVAL_DIR, "report.md")

STRATA = {"random": 70, "no_german": 20, "pay_text": 10}
SEED = 20261010

# Skills checked for recall: frequent ones plus the ones a business/IT student
# cares about. Labelling every skill of a posting would take far too long.
PANEL = [
    "ms_office", "excel", "powerpoint", "sap", "sql", "python", "java", "javascript",
    "powerbi", "git", "controlling", "accounting", "social_media", "driving_licence",
]
GERMAN_LEVELS = ["required", "plus", "none", "implicit"]


# --- Sampling ------------------------------------------------------------------------

def draw_sample():
    with open(JOBS_CSV, newline="", encoding="utf-8") as f:
        jobs = list(csv.DictReader(f))
    last_day = max(j["last_seen"] for j in jobs)
    texts = load_detail_cache()
    pool = [j for j in jobs if j["last_seen"] == last_day and j["detail_ok"] == "1"
            and (texts.get(j["refnr"]) or {}).get("stellenangebotsBeschreibung")]

    rng = random.Random(SEED)
    picked, chosen = [], set()

    def take(stratum, candidates, n):
        candidates = [j for j in candidates if j["refnr"] not in chosen]
        for j in rng.sample(candidates, min(n, len(candidates))):
            picked.append((stratum, j))
            chosen.add(j["refnr"])

    take("random", pool, STRATA["random"])
    take("no_german", [j for j in pool if j["german"] in ("none", "plus")], STRATA["no_german"])
    take("pay_text", [j for j in pool if j["pay_src"] == "text"], STRATA["pay_text"])
    rng.shuffle(picked)

    os.makedirs(EVAL_DIR, exist_ok=True)
    sample = [{
        "refnr": j["refnr"],
        "title": j["title"],
        "company": j["company"],
        "city": j["city"],
        "hauptberuf": j["hauptberuf"],
        "url": f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{j['refnr']}",
        "text": texts[j["refnr"]]["stellenangebotsBeschreibung"],
    } for _, j in picked]
    with open(SAMPLE_JSON, "w", encoding="utf-8") as f:
        json.dump({
            "panel": [{"id": sid, "label": label} for sid, label in panel_labels()],
            "categories": [{"id": cid, "label": label} for cid, label, _ in CATEGORIES] + [{"id": "other", "label": "Other"}],
            "postings": sample,
        }, f, ensure_ascii=False, indent=1)
    with open(SAMPLE_IDS, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["refnr", "stratum"])
        w.writerows([(j["refnr"], s) for s, j in picked])
    print(f"wrote {len(sample)} postings to {os.path.relpath(SAMPLE_JSON, ROOT)} "
          f"({Counter(s for s, _ in picked)})")


def panel_labels():
    from .skills import SKILLS
    labels = {sid: label for sid, label, _, _ in SKILLS}
    return [(sid, labels[sid]) for sid in PANEL]


# --- Report --------------------------------------------------------------------------

def predictions(sample):
    """Re-run the current rules on the stored texts (not the CSV), so the report
    always describes the code as it is now."""
    preds = {}
    for p in sample["postings"]:
        listing = {"stellenangebotsTitel": p["title"], "hauptberuf": p.get("hauptberuf"),
                   "stellenlokationen": [{"adresse": {"ort": p["city"]}}]}
        f = extract(listing, {"stellenangebotsBeschreibung": p["text"]})
        preds[p["refnr"]] = f
    return preds


def pct(n, d):
    return f"{n / d:.0%}" if d else "–"


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    f1 = 2 * p * r / (p + r) if p and r else None
    fmt = lambda v: "–" if v is None else f"{v:.0%}"
    return fmt(p), fmt(r), fmt(f1)


def build_report(sample, labels, strata, preds):
    lines = ["# Extraction accuracy", "", f"Rules: extractor version {EXTRACTOR_VERSION}.", ""]
    lab = {r["refnr"]: r for r in labels}
    n_total = len(lab)
    rnd = [ref for ref in lab if strata.get(ref) == "random"]
    lines += [
        f"Labelled postings: **{n_total}** (random sample: {len(rnd)}). "
        "Labelling was blind: the labeller saw the posting text, not the predictions "
        "(how the labels were made: [LABELS.md](LABELS.md)). "
        "Predictions come from re-running the rules on the same texts.",
        "",
    ]

    # Werkstudent filter and field
    ws = [ref for ref in rnd if lab[ref]["is_werkstudent"] in ("0", "1")]
    ok = sum(lab[ref]["is_werkstudent"] == "1" for ref in ws)
    cat = [ref for ref in rnd if lab[ref]["category"]]
    cat_ok = sum(lab[ref]["category"] == preds[ref]["category"] for ref in cat)
    lines += [
        "## Werkstudent filter and job field (random sample)", "",
        "| Check | Result |", "|---|---|",
        f"| Posting really is a Werkstudent job | {ok}/{len(ws)} ({pct(ok, len(ws))}) |",
        f"| Job field assigned correctly | {cat_ok}/{len(cat)} ({pct(cat_ok, len(cat))}) |",
        "",
    ]

    # German
    g = [ref for ref in rnd if lab[ref]["german"] in GERMAN_LEVELS]
    exact = sum(lab[ref]["german"] == preds[ref]["german"] for ref in g)
    open_ = lambda v: v in ("none", "plus")
    binary = sum(open_(lab[ref]["german"]) == open_(preds[ref]["german"]) for ref in g)
    claimed = [ref for ref in lab if open_(preds[ref]["german"]) and lab[ref]["german"] in GERMAN_LEVELS]
    claimed_ok = sum(open_(lab[ref]["german"]) for ref in claimed)
    lines += [
        "## German requirement", "",
        "| Check | Result |", "|---|---|",
        f"| Exact level (required / plus / none / not mentioned), random sample | {exact}/{len(g)} ({pct(exact, len(g))}) |",
        f"| Open to non-German speakers yes/no, random sample | {binary}/{len(g)} ({pct(binary, len(g))}) |",
        f"| Postings shown as “open without German” that really are (all strata) | {claimed_ok}/{len(claimed)} ({pct(claimed_ok, len(claimed))}) |",
        "",
        "Confusion matrix, random sample (rows: label, columns: rules):", "",
        "| label \\ rules | " + " | ".join(GERMAN_LEVELS) + " |",
        "|---|" + "---|" * len(GERMAN_LEVELS),
    ]
    cm = Counter((lab[ref]["german"], preds[ref]["german"]) for ref in g)
    for a in GERMAN_LEVELS:
        lines.append(f"| {a} | " + " | ".join(str(cm[(a, b)]) for b in GERMAN_LEVELS) + " |")
    lines.append("")

    # Pay
    def has_pay(r):
        return bool(r.get("pay_min"))

    def same_pay(l, p):
        return abs(float(l["pay_min"]) - float(p["pay_min"])) < 0.01 and \
            abs(float(l["pay_max"] or l["pay_min"]) - float(p["pay_max"])) < 0.01

    tp = sum(has_pay(lab[ref]) and has_pay(preds[ref]) for ref in rnd)
    fp = sum(not has_pay(lab[ref]) and has_pay(preds[ref]) for ref in rnd)
    fn = sum(has_pay(lab[ref]) and not has_pay(preds[ref]) for ref in rnd)
    p, r, _ = prf(tp, fp, fn)
    found = [ref for ref in lab if has_pay(preds[ref]) and has_pay(lab[ref])]
    right = sum(same_pay(lab[ref], preds[ref]) for ref in found)
    text_found = [ref for ref in lab if preds[ref]["pay_src"] == "text"]
    text_right = sum(has_pay(lab[ref]) and same_pay(lab[ref], preds[ref]) for ref in text_found)
    lines += [
        "## Hourly pay", "",
        "Pay fields from the API aren't part of this check (the texts are re-analysed alone), so this measures the text rules.", "",
        "| Check | Result |", "|---|---|",
        f"| Precision: rules find a rate and the posting states one, random sample | {p} ({tp}/{tp + fp}) |",
        f"| Recall: posting states a rate and the rules find it, random sample | {r} ({tp}/{tp + fn}) |",
        f"| Amount correct when both found it (all strata) | {right}/{len(found)} ({pct(right, len(found))}) |",
        f"| Rates found in the text that are correct (all strata) | {text_right}/{len(text_found)} ({pct(text_right, len(text_found))}) |",
        "",
    ]

    # Skills
    rows, TP, FP, FN = [], 0, 0, 0
    for sid, label in panel_labels():
        tp = fp = fn = 0
        for ref in rnd:
            truth = sid in lab[ref]["skills"].split("|")
            pred = sid in preds[ref]["skills"].split("|")
            tp += truth and pred
            fp += pred and not truth
            fn += truth and not pred
        TP, FP, FN = TP + tp, FP + fp, FN + fn
        p, r, f1 = prf(tp, fp, fn)
        rows.append(f"| {label} | {tp + fn} | {p} | {r} | {f1} |")
    p, r, f1 = prf(TP, FP, FN)
    lines += [
        f"## Skills ({len(PANEL)} common skills, random sample)", "",
        "| Skill | In postings | Precision | Recall | F1 |", "|---|---|---|---|---|",
        *rows,
        f"| **All {len(PANEL)}** | {TP + FN} | **{p}** | **{r}** | **{f1}** |",
        "",
    ]

    # Disagreements, for improving the rules (reference numbers only, no texts)
    diffs = []
    for ref in lab:
        l, pr = lab[ref], preds[ref]
        if l["german"] in GERMAN_LEVELS and l["german"] != pr["german"]:
            diffs.append(f"| {ref} | German | {l['german']} | {pr['german']} |")
        if has_pay(l) != has_pay(pr) or (has_pay(l) and has_pay(pr) and not same_pay(l, pr)):
            diffs.append(f"| {ref} | pay | {l['pay_min']}–{l['pay_max']} | {pr['pay_min']}–{pr['pay_max']} |")
    lines += ["## Disagreements", "", "| Posting | Field | Label | Rules |", "|---|---|---|---|", *diffs, ""]
    return "\n".join(lines)


def report():
    with open(SAMPLE_JSON, encoding="utf-8") as f:
        sample = json.load(f)
    with open(SAMPLE_IDS, newline="", encoding="utf-8") as f:
        strata = {r["refnr"]: r["stratum"] for r in csv.DictReader(f)}
    with open(LABELS_CSV, newline="", encoding="utf-8") as f:
        labels = [r for r in csv.DictReader(f) if r["refnr"] in strata]
    preds = predictions(sample)
    text = build_report(sample, labels, strata, preds)
    with open(REPORT_MD, "w", encoding="utf-8") as f:
        f.write(text)
    print(text)
    print(f"\nwrote {os.path.relpath(REPORT_MD, ROOT)}")


# --- Labelling server ----------------------------------------------------------------

class LabelHandler(SimpleHTTPRequestHandler):
    """Serves the repo (for eval/label.html and the sample) and stores labels on POST /labels."""

    def do_GET(self):
        if self.path == "/labels":
            rows = []
            if os.path.exists(LABELS_CSV):
                with open(LABELS_CSV, newline="", encoding="utf-8") as f:
                    rows = list(csv.DictReader(f))
            return self._json(rows)
        if self.path == "/":
            self.send_response(302)
            self.send_header("Location", "/eval/label.html")
            return self.end_headers()
        return super().do_GET()

    def do_POST(self):
        if self.path != "/labels":
            return self.send_error(404)
        rows = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        os.makedirs(EVAL_DIR, exist_ok=True)
        tmp = LABELS_CSV + ".tmp"
        with open(tmp, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=LABEL_FIELDS, extrasaction="ignore", lineterminator="\n")
            w.writeheader()
            w.writerows(sorted(rows, key=lambda r: r["refnr"]))
        os.replace(tmp, LABELS_CSV)
        self._json({"saved": len(rows)})

    def _json(self, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def serve_labeller():
    if not os.path.exists(SAMPLE_JSON):
        raise SystemExit("no sample yet; run `python -m radar.evaluate sample` first")
    server = ThreadingHTTPServer(("127.0.0.1", LABEL_PORT), partial(LabelHandler, directory=ROOT))
    print(f"Labelling form: http://localhost:{LABEL_PORT}/  (Ctrl+C to stop; labels are saved after every posting)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["sample", "label", "report"])
    args = parser.parse_args()
    {"sample": draw_sample, "label": serve_labeller, "report": report}[args.command]()


if __name__ == "__main__":
    main()
