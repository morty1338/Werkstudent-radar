"""Tests for the SQL aggregation step on a small synthetic jobs.csv."""

import csv

import pytest

from radar import build
from radar.enrich import FIELDS


def job(refnr, **kw):
    row = {f: "" for f in FIELDS}
    row.update({
        "refnr": refnr, "title": f"Werkstudent {refnr}", "company": f"Company {refnr}",
        "city": "Berlin", "category": "it", "lang": "de", "german": "implicit",
        "skills": "", "majors": "", "remote": "0", "external": "0",
        "published": "2026-10-01", "first_seen": "2026-10-01", "last_seen": "2026-10-09",
        "detail_ok": "1", "xv": "2",
    })
    row.update({k: str(v) for k, v in kw.items()})
    return row


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


@pytest.fixture
def db(tmp_path):
    rows = [
        job("a", pay_min=14, pay_max=16, skills="sql|python", german="none"),
        job("b", pay_min=18, pay_max=18, skills="sql", german="plus"),
        job("c", pay_min=20, pay_max=20, skills="excel", german="required", category="marketing"),
        # the same role posted in three cities: counts once nationally, once per city
        job("d1", title="Same role", company="Chain", pay_min=13, pay_max=13, city="Berlin"),
        job("d2", title="Same role", company="Chain", pay_min=13, pay_max=13, city="Hamburg"),
        job("d3", title="Same role", company="Chain", pay_min=13, pay_max=13, city="München"),
        # no longer online: excluded from every figure
        job("old", pay_min=40, pay_max=40, last_seen="2026-10-01"),
    ]
    path = tmp_path / "jobs.csv"
    write_csv(path, rows)
    return build.load_db(path)


def test_percentile_interpolates():
    agg = build.Percentile()
    for v in [10, 20, 30, 40]:
        agg.step(v, 0.5)
    agg.step(None, 0.5)
    assert agg.finalize() == 25.0


def test_totals_only_count_active_and_dedupe_roles(db):
    t = build.query(db, "totals")[0]
    assert t["jobs"] == 6
    assert t["postings_with_pay"] == 6
    assert t["with_pay"] == 4           # the chain's role counts once
    assert t["median_pay"] == 16.5      # median of 15, 18, 20, 13
    assert t["no_german"] == 2


def test_city_pay_counts_role_once_per_city(db):
    cities = {c["city"]: c for c in build.query(db, "cities", min_jobs=1)}
    assert cities["Berlin"]["with_pay"] == 4
    assert cities["Hamburg"]["with_pay"] == 1


def test_skill_shares(db):
    skills = {s["id"]: s for s in build.query(db, "skills")}
    assert skills["sql"]["jobs"] == 2
    assert skills["sql"]["share"] == round(2 / 6, 4)
    assert skills["sql"]["median_pay"] == 16.5


def test_employer_concentration(db):
    cats = {c["key"]: c for c in build.query(db, "categories")}
    assert cats["it"]["pay_employers"] == 3
    assert cats["it"]["top_employer_share"] == round(1 / 3, 3)


def test_small_samples_hide_median():
    rows = build.hide_small_medians([
        {"median_pay": 16.0, "with_pay": 9, "pay_employers": 9},
        {"median_pay": 16.0, "with_pay": 30, "pay_employers": 2},
        {"median_pay": 16.0, "with_pay": 30, "pay_employers": 10},
    ])
    assert [r["median_pay"] for r in rows] == [None, None, 16.0]


def test_history_replaces_same_day(db, tmp_path):
    path = tmp_path / "history.csv"
    first = build.update_history(db, "2026-10-09", path)
    again = build.update_history(db, "2026-10-09", path)
    assert len(first) == len(again)
    total = next(r for r in again if r["dim"] == "total")
    assert total["jobs"] == 6


def test_checker_uses_indices(db):
    summary = {"as_of": "2026-10-09", "skills": build.query(db, "skills"),
               "categories": build.query(db, "categories"), "cities": build.query(db, "cities", min_jobs=1)}
    build.MIN_CHECKER_SKILL_JOBS, saved = 1, build.MIN_CHECKER_SKILL_JOBS
    try:
        checker = build.build_checker(db, summary)
    finally:
        build.MIN_CHECKER_SKILL_JOBS = saved
    assert len(checker["jobs"]) == 6
    skill_ids = [s["id"] for s in checker["skills"]]
    job_a = next(j for j in checker["jobs"] if j[3] == 15.0)
    assert sorted(skill_ids[i] for i in job_a[4]) == ["python", "sql"]
