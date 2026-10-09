"""Tests for the evaluation report on a synthetic sample."""

from radar import evaluate


def sample():
    texts = {
        "a": "Wir suchen dich. Sehr gute Deutschkenntnisse. Vergütung: 16 € pro Stunde. Kenntnisse in Excel und SQL.",
        "b": "Working Student Data. You know Python and SQL. Our working language is English.",
        "c": "Werkstudent im Einkauf. Du bist motiviert und arbeitest gern im Team.",
    }
    return {"postings": [
        {"refnr": ref, "title": f"Werkstudent {ref}", "company": "X", "city": "Berlin", "hauptberuf": "", "text": t}
        for ref, t in texts.items()
    ]}


def labels_from(preds, **overrides):
    rows = []
    for ref, p in preds.items():
        row = {"refnr": ref, "is_werkstudent": "1", "category": p["category"], "german": p["german"],
               "pay_min": p["pay_min"], "pay_max": p["pay_max"], "skills": p["skills"], "note": ""}
        row.update(overrides.get(ref, {}))
        rows.append(row)
    return rows


def test_perfect_labels_score_full_marks():
    s = sample()
    preds = evaluate.predictions(s)
    strata = {ref: "random" for ref in preds}
    report = evaluate.build_report(s, labels_from(preds), strata, preds)
    assert "| Exact level (required / plus / none / not mentioned), random sample | 3/3 (100%) |" in report
    assert "| Amount correct when both found it (all strata) | 1/1 (100%) |" in report
    assert "## Disagreements" in report
    assert report.rstrip().endswith("|---|---|---|---|")  # no disagreement rows


def test_disagreements_are_listed_without_text():
    s = sample()
    preds = evaluate.predictions(s)
    strata = {ref: "random" for ref in preds}
    labels = labels_from(preds, c={"german": "required", "pay_min": "15.00", "pay_max": "15.00"})
    report = evaluate.build_report(s, labels, strata, preds)
    assert "| c | German | required | implicit |" in report
    assert "| c | pay | 15.00–15.00 | – |" in report
    assert "Einkauf" not in report  # posting texts never end up in the report
