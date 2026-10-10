"""Tests for the posting history: upserts, online stretches, text tables, timeline."""

import csv

import pytest

from radar import history

D1, D2, D3, D4 = "2026-10-01", "2026-10-02", "2026-10-03", "2026-10-04"


def stretches(db):
    return [tuple(r) for r in db.execute("SELECT refnr, start_date, end_date FROM online ORDER BY refnr, start_date")]


def job(refnr, **kw):
    row = {"refnr": refnr, "source": "ba", "company": "Acme", "first_seen": D1, "last_seen": D1,
           "category": "it", "city": "Berlin", "lat": "52.52", "lon": "13.40", "pay_min": "", "pay_max": "",
           "german": "required", "skills": ""}
    row.update({k: str(v) for k, v in kw.items()})
    return row


@pytest.fixture
def db():
    return history.connect()


# --- Online stretches ---------------------------------------------------------------------

def test_postings_missing_from_a_scan_end_at_the_scan_before(db):
    history.record_scan(db, D1, {"ba": {"a", "b"}})
    stats = history.record_scan(db, D2, {"ba": {"b", "c"}})
    assert stats == {"online": 2, "started": 1, "ended": 1}
    assert stretches(db) == [("a", D1, D1), ("b", D1, None), ("c", D2, None)]


def test_a_posting_that_comes_back_gets_a_new_stretch(db):
    history.record_scan(db, D1, {"ba": {"a"}})
    history.record_scan(db, D2, {"ba": set()})
    history.record_scan(db, D3, {"ba": {"a"}})
    assert stretches(db) == [("a", D1, D1), ("a", D3, None)]


def test_a_skipped_day_is_not_a_gap(db):
    # No scan on D2 (the run didn't happen): the stretch continues from D1 to D3.
    history.record_scan(db, D1, {"ba": {"a"}})
    history.record_scan(db, D3, {"ba": {"a"}})
    assert stretches(db) == [("a", D1, None)]


def test_recording_the_latest_day_again_replaces_it(db):
    history.record_scan(db, D1, {"ba": {"a", "b"}})
    history.record_scan(db, D2, {"ba": {"b", "c"}})
    first = stretches(db)
    history.record_scan(db, D2, {"ba": {"a"}})          # different answer the second time
    assert stretches(db) == [("a", D1, None), ("b", D1, D1)]
    history.record_scan(db, D2, {"ba": {"b", "c"}})     # and back
    assert stretches(db) == first
    assert db.execute("SELECT COUNT(*) FROM scans WHERE date = ?", (D2,)).fetchone()[0] == 1


def test_scans_must_come_in_date_order(db):
    history.record_scan(db, D2, {"ba": {"a"}})
    with pytest.raises(ValueError):
        history.record_scan(db, D1, {"ba": {"a"}})


def test_scans_are_counted_per_source(db):
    history.record_scan(db, D1, {"ba": {"a", "b"}, "arbeitnow": {"an:x"}})
    assert [tuple(r) for r in db.execute("SELECT * FROM scans ORDER BY source")] == [(D1, "arbeitnow", 1), (D1, "ba", 2)]


# --- Postings upsert ---------------------------------------------------------------------------

def test_upsert_inserts_then_updates_in_place(db):
    history.upsert_postings(db, [job("a", pay_min=14, pay_max=16, skills="sql|python", german="none")])
    history.upsert_postings(db, [job("a", last_seen=D3, city="Hamburg", skills="sql")])
    p = dict(db.execute("SELECT * FROM postings").fetchone())
    assert (p["first_seen"], p["last_seen"], p["city"]) == (D1, D3, "Hamburg")
    assert [r[0] for r in db.execute("SELECT skill FROM posting_skills")] == ["sql"]


def test_upsert_never_moves_last_seen_back(db):
    history.upsert_postings(db, [job("a", first_seen=D2, last_seen=D3)])
    history.upsert_postings(db, [job("a", first_seen=D1, last_seen=D2)])   # an older copy of the row
    p = db.execute("SELECT first_seen, last_seen FROM postings").fetchone()
    assert tuple(p) == (D1, D3)


@pytest.mark.parametrize("german, required", [("required", 1), ("implicit", 1), ("plus", 0), ("none", 0), ("", None)])
def test_german_required_follows_the_sites_rule(db, german, required):
    history.upsert_postings(db, [job("a", german=german)])
    assert db.execute("SELECT german_required FROM postings").fetchone()[0] == required


def test_pay_is_the_midpoint_and_missing_pay_stays_null(db):
    history.upsert_postings(db, [job("a", pay_min=14, pay_max=17), job("b", pay_min=15), job("c")])
    assert dict(db.execute("SELECT refnr, pay FROM postings").fetchall()) == {"a": 15.5, "b": 15.0, "c": None}


# --- Text tables ---------------------------------------------------------------------------------

def test_text_tables_round_trip(db, tmp_path):
    history.record_scan(db, D1, {"ba": {"a", "b"}})
    history.record_scan(db, D2, {"ba": {"b"}, "arbeitnow": {"an:x"}})
    history.dump_tables(db, tmp_path)
    with open(tmp_path / "online.csv", newline="") as f:
        assert list(csv.reader(f)) == [["refnr", "start_date", "end_date"], ["a", D1, D1], ["b", D1, ""], ["an:x", D2, ""]]
    again = history.connect()
    history.load_tables(again, tmp_path)
    assert stretches(again) == stretches(db)
    assert again.execute("SELECT * FROM scans ORDER BY date, source").fetchall() == \
        db.execute("SELECT * FROM scans ORDER BY date, source").fetchall()


# --- Timeline -------------------------------------------------------------------------------------

def test_timeline_counts_new_back_and_gone(db):
    history.record_scan(db, D1, {"ba": {"a", "b"}})
    history.record_scan(db, D2, {"ba": {"b", "c"}})                         # a gone, c new
    history.record_scan(db, D3, {"ba": {"a", "b", "c"}, "arbeitnow": {"x"}})  # a back, x new
    t = history.timeline(db)
    assert t["dates"] == [D1, D2, D3]
    assert t["online"] == [2, 2, 4]
    assert t["new"] == [None, 1, 1]
    assert t["back"] == [None, 0, 1]
    assert t["gone"] == [None, 1, 0]
    assert t["by_source"] == {"arbeitnow": [None, None, 1], "ba": [2, 2, 3]}


# --- End to end -----------------------------------------------------------------------------------

def test_backfill_then_a_daily_run_on_the_same_day_changes_nothing(tmp_path):
    jobs = [job("a", first_seen=D1, last_seen=D2), job("b", first_seen=D1, last_seen=D3),
            job("c", first_seen=D3, last_seen=D3, source="arbeitnow")]
    paths = {"history_dir": tmp_path / "h", "db_path": str(tmp_path / "h.sqlite"), "timeline_path": tmp_path / "t.json"}
    _, t = history.run(jobs, backfill_from=[], **paths)
    assert t["dates"] == [D2, D3] and t["online"] == [2, 2]
    before = (tmp_path / "h" / "online.csv").read_text()
    history.run(jobs, **paths)
    assert (tmp_path / "h" / "online.csv").read_text() == before


def test_daily_run_appends_a_scan_and_keeps_last_seen_of_missing_postings(tmp_path):
    paths = {"history_dir": tmp_path / "h", "db_path": str(tmp_path / "h.sqlite"), "timeline_path": tmp_path / "t.json"}
    history.run([job("a", last_seen=D1), job("b", last_seen=D1)], **paths)
    stats, t = history.run([job("a", last_seen=D1), job("b", last_seen=D4), job("c", first_seen=D4, last_seen=D4)], **paths)
    assert stats == {"online": 2, "started": 1, "ended": 1}
    assert t["gone"] == [None, 1] and t["new"] == [None, 1]
    db = history.sqlite3.connect(paths["db_path"])
    assert db.execute("SELECT last_seen FROM postings WHERE refnr = 'a'").fetchone()[0] == D1
    assert db.execute("SELECT still_online FROM lifetimes WHERE refnr = 'b'").fetchone()[0] == 1
