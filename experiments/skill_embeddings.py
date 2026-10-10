"""Experiment: find skills with multilingual sentence embeddings instead of rules.

Compares three ways of deciding whether a posting asks for a skill, on the 100
labelled postings in data/eval/ (14 skills are labelled, see radar/evaluate.py):

    rules        the regex rules the pipeline uses (radar/extract.py)
    embeddings   the posting is cut into phrases; each skill has a few hand-written
                 anchor phrases (German and English); a skill counts when some
                 phrase is close enough to some anchor (cosine similarity)
    combined     rules OR embeddings, and rules AND embeddings

The similarity threshold is chosen by 5-fold cross-validation over postings, so
the embedding scores are not tuned on the postings they are measured on.

Usage (local only: the job texts in data/eval/sample.json are not published):
    python3 -m venv experiments/.venv
    experiments/.venv/bin/pip install -r experiments/requirements.txt
    experiments/.venv/bin/python experiments/skill_embeddings.py [--model NAME]

Writes experiments/report.md (scores and reference numbers only, no job text).
The model is downloaded once into experiments/.cache/ (git-ignored).
"""

import argparse
import csv
import json
import os
import random
import re
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from radar.evaluate import LABELS_CSV, PANEL, SAMPLE_IDS, SAMPLE_JSON, predictions  # noqa: E402
from radar.skills import SKILLS  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPORT_MD = os.path.join(HERE, "report.md")
CACHE_DIR = os.path.join(HERE, ".cache")
DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
FOLDS = 5
SEED = 7

# What a posting says when it wants the skill. Written by hand from how postings
# phrase it, independent of the regexes.
ANCHORS = {
    "ms_office": ["MS Office Kenntnisse", "sicherer Umgang mit Microsoft Office", "proficient in Microsoft Office",
                  "gute Kenntnisse der Office-Anwendungen"],
    "excel": ["sehr gute Excel-Kenntnisse", "advanced Excel skills", "Erfahrung mit Microsoft Excel und Pivot-Tabellen"],
    "powerpoint": ["Erstellung von PowerPoint-Präsentationen", "good PowerPoint skills", "sicherer Umgang mit PowerPoint"],
    "sap": ["SAP-Kenntnisse", "Erfahrung mit SAP S/4HANA", "experience with SAP"],
    "sql": ["SQL-Kenntnisse", "Datenbankabfragen mit SQL", "experience with SQL databases"],
    "python": ["Programmierkenntnisse in Python", "experience in Python programming", "Datenanalyse mit Python"],
    "java": ["Programmierkenntnisse in Java", "Java development experience", "Softwareentwicklung mit Java"],
    "javascript": ["JavaScript-Kenntnisse", "web development with JavaScript", "Frontend-Entwicklung mit JavaScript"],
    "powerbi": ["Erstellung von Power BI Dashboards", "experience with Power BI", "Reporting mit Power BI"],
    "git": ["Versionsverwaltung mit Git", "experience with Git and GitHub"],
    "controlling": ["Unterstützung im Controlling und Reporting", "Erstellung von Reports, Budgets und Forecasts",
                    "financial controlling and reporting"],
    "accounting": ["Unterstützung der Buchhaltung", "Kreditoren- und Debitorenbuchhaltung", "accounting and bookkeeping"],
    "social_media": ["Betreuung unserer Social-Media-Kanäle", "Content für Instagram, LinkedIn und TikTok",
                     "social media management"],
    "driving_licence": ["Führerschein Klasse B", "valid driver's license", "Fahrerlaubnis erforderlich"],
}


# --- Data ---------------------------------------------------------------------------------

def load():
    with open(SAMPLE_JSON, encoding="utf-8") as f:
        sample = json.load(f)
    with open(LABELS_CSV, newline="", encoding="utf-8") as f:
        labels = {r["refnr"]: set(filter(None, r["skills"].split("|"))) for r in csv.DictReader(f)}
    with open(SAMPLE_IDS, newline="", encoding="utf-8") as f:
        strata = {r["refnr"]: r["stratum"] for r in csv.DictReader(f)}
    postings = [p for p in sample["postings"] if p["refnr"] in labels]
    return postings, labels, strata


def phrases(title, text, max_words=40, stride=20):
    """Bullet points and sentences of a posting; long ones as overlapping windows."""
    parts = [title] + re.split(r"\n+|(?<=[.!?;:])\s+|\s[•·▪–-]\s|\s\*\s", text or "")
    out = []
    for part in parts:
        words = part.split()
        if len(words) < 2:
            continue
        if len(words) <= max_words:
            out.append(" ".join(words))
        else:
            out += [" ".join(words[i:i + max_words]) for i in range(0, len(words) - stride, stride)]
    return out


# --- Embeddings ---------------------------------------------------------------------------

def embed(model, texts):
    vecs = np.array(list(model.embed(texts, batch_size=64)), dtype=np.float32)
    return vecs / np.linalg.norm(vecs, axis=1, keepdims=True)


def skill_scores(model, postings):
    """scores[refnr][skill] = best cosine similarity of any phrase to any anchor."""
    anchor_list = [(sid, a) for sid in PANEL for a in ANCHORS[sid]]
    A = embed(model, [a for _, a in anchor_list])
    owner = np.array([PANEL.index(sid) for sid, _ in anchor_list])
    scores = {}
    for p in postings:
        P = embed(model, phrases(p["title"], p["text"]))
        sims = P @ A.T                                     # phrases x anchors
        best = sims.max(axis=0)                            # per anchor
        scores[p["refnr"]] = {sid: float(best[owner == k].max()) for k, sid in enumerate(PANEL)}
    return scores


# --- Scoring --------------------------------------------------------------------------------

def counts(refs, truth, pred):
    """{skill: [tp, fp, fn]} over postings refs; truth/pred: refnr -> set of skills."""
    c = {sid: [0, 0, 0] for sid in PANEL}
    for ref in refs:
        for sid in PANEL:
            t, p = sid in truth[ref], sid in pred[ref]
            c[sid][0] += t and p
            c[sid][1] += p and not t
            c[sid][2] += t and not p
    return c


def micro(c):
    tp, fp, fn = (sum(v[i] for v in c.values()) for i in range(3))
    return tp, fp, fn


def f1(tp, fp, fn):
    return 2 * tp / (2 * tp + fp + fn) if tp else 0.0


def by_threshold(scores, refs, thr):
    return {ref: {sid for sid, s in scores[ref].items() if s >= thr} for ref in refs}


def best_threshold(scores, truth, refs, grid):
    return max(grid, key=lambda thr: (f1(*micro(counts(refs, truth, by_threshold(scores, refs, thr)))), -thr))


def cross_validated(scores, truth, refs, grid):
    """Out-of-fold predictions: each fold is predicted with a threshold picked on the others."""
    order = refs[:]
    random.Random(SEED).shuffle(order)
    folds = [order[i::FOLDS] for i in range(FOLDS)]
    pred, chosen = {}, []
    for k, test in enumerate(folds):
        train = [r for j, f in enumerate(folds) if j != k for r in f]
        thr = best_threshold(scores, truth, train, grid)
        chosen.append(thr)
        pred.update(by_threshold(scores, test, thr))
    return pred, chosen


# --- Report ------------------------------------------------------------------------------------

def pct(v):
    return "–" if v is None else f"{v:.0%}"


def prf_cells(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    return pct(p), pct(r), pct(f1(tp, fp, fn) if tp + fn else None) if tp + fn else "–"


def table(methods, refs, truth, labels):
    head = "| Skill | In postings | " + " | ".join(f"{m} P / R / F1" for m in methods) + " |"
    rows = [head, "|---|---|" + "---|" * len(methods)]
    per = {m: counts(refs, truth, pred) for m, pred in methods.items()}
    for sid in PANEL:
        support = per[next(iter(methods))][sid][0] + per[next(iter(methods))][sid][2]
        cells = [" / ".join(prf_cells(*per[m][sid])) for m in methods]
        rows.append(f"| {labels[sid]} | {support} | " + " | ".join(cells) + " |")
    totals = [micro(per[m]) for m in methods]
    support = totals[0][0] + totals[0][2]
    rows.append(f"| **All {len(PANEL)} (micro)** | {support} | "
                + " | ".join("**" + " / ".join(prf_cells(*t)) + "**" for t in totals) + " |")
    return rows, {m: micro(per[m]) for m in methods}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()
    from fastembed import TextEmbedding

    postings, truth, strata = load()
    refs = [p["refnr"] for p in postings]
    labels = {sid: label for sid, label, _, _ in SKILLS}
    rule_preds = {ref: set(filter(None, f["skills"].split("|"))) & set(PANEL) for ref, f in predictions({"postings": postings}).items()}

    t0 = time.time()
    model = TextEmbedding(args.model, cache_dir=CACHE_DIR)
    load_s = time.time() - t0
    t0 = time.time()
    scores = skill_scores(model, postings)
    embed_s = time.time() - t0

    grid = [round(x, 2) for x in np.arange(0.40, 0.951, 0.01)]
    emb_pred, chosen = cross_validated(scores, truth, refs, grid)
    union = {ref: rule_preds[ref] | emb_pred[ref] for ref in refs}
    inter = {ref: rule_preds[ref] & emb_pred[ref] for ref in refs}
    methods = {"Rules": rule_preds, "Embeddings": emb_pred, "Rules ∪ emb.": union, "Rules ∩ emb.": inter}

    rows_all, tot_all = table(methods, refs, truth, labels)
    rnd = [r for r in refs if strata.get(r) == "random"]
    rows_rnd, tot_rnd = table(methods, rnd, truth, labels)
    oracle = best_threshold(scores, truth, refs, grid)
    oracle_f1 = f1(*micro(counts(refs, truth, by_threshold(scores, refs, oracle))))

    # Where the embeddings go wrong, by reference number and score only.
    errors = []
    for ref in refs:
        for sid in PANEL:
            if (sid in emb_pred[ref]) != (sid in truth[ref]):
                kind = "false positive" if sid in emb_pred[ref] else "missed"
                errors.append((kind, labels[sid], ref, scores[ref][sid], sid in rule_preds[ref]))
    errors.sort(key=lambda e: (e[0], -e[3] if e[0] == "false positive" else e[3]))

    f1s = {m: f1(*t) for m, t in tot_all.items()}
    best = max(f1s, key=f1s.get)
    lines = [
        "# Skill extraction: sentence embeddings vs. rules", "",
        f"Model: `{args.model}` via fastembed (ONNX, CPU). Loading took {load_s:.0f} s, scoring "
        f"{len(postings)} postings {embed_s:.0f} s ({1000 * embed_s / len(postings):.0f} ms per posting).", "",
        "Ground truth: the 100 labelled postings in `data/eval/` (14 skills; labels made by an AI assistant, "
        "see [LABELS.md](../data/eval/LABELS.md)). Embedding thresholds were picked by 5-fold cross-validation "
        f"over postings (chosen per fold: {', '.join(f'{c:.2f}' for c in chosen)}); the best single threshold "
        f"on all postings would be {oracle:.2f} (micro F1 {oracle_f1:.0%}, optimistic).", "",
        "Caveat in the rules' favour: the rules were improved after looking at disagreements on these same "
        "postings ([report_baseline.md](../data/eval/report_baseline.md) has their earlier, honest score on the "
        "random sample: micro F1 97%, vs. 98% now). The embeddings saw none of the labels except through the threshold.", "",
        "## All 100 postings", "", *rows_all, "",
        "## Random sample (70 postings, comparable with data/eval/report.md)", "", *rows_rnd, "",
        "## Where the embeddings go wrong", "",
        "Reference numbers and similarity scores only (job texts are not published). "
        "“Rules” says whether the rules got that case right.", "",
        "| Error | Skill | Posting | Similarity | Rules right? |", "|---|---|---|---|---|",
        *[f"| {k} | {s} | {r} | {sc:.2f} | {'yes' if (rp if k == 'missed' else not rp) else 'no'} |"
          for k, s, r, sc, rp in errors[:25]],
        f"{'' if len(errors) <= 25 else f'| … {len(errors) - 25} more | | | | |'}", "",
        "## Result", "",
        f"Micro F1 on all 100 postings: " + ", ".join(f"{m} {v:.0%}" for m, v in f1s.items()) + f". Best: **{best}**.",
        "",
    ]
    with open(REPORT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("\n".join(rows_all))
    print(f"\nthresholds per fold: {chosen}; oracle {oracle} (F1 {oracle_f1:.3f}); embed {embed_s:.1f}s")
    print({m: round(v, 3) for m, v in f1s.items()})
    print(f"wrote {os.path.relpath(REPORT_MD, ROOT)}")


if __name__ == "__main__":
    main()
