"""Tests for the data-quality checks of the daily run."""

import pytest

from radar import checks

DAY = "2026-10-10"


def scans(*counts, source="ba"):
    """Scans on consecutive days ending on DAY: counts[-1] is today's."""
    days = [f"2026-10-{10 - i:02d}" for i in range(len(counts))][::-1]
    return [{"date": d, "source": source, "postings": str(n)} for d, n in zip(days, counts)]


def status(results, check):
    return next(r.status for r in results if r.check == check)


# --- Volume ------------------------------------------------------------------------------

@pytest.mark.parametrize("counts, expected", [
    ((4000, 4100, 4200, 4150), "ok"),
    ((4000, 4100, 4200, 6100), "ok"),          # +49%
    ((4000, 4100, 4200, 6300), "fail"),        # +54%
    ((4000, 4100, 4200, 1900), "fail"),        # −54%
    ((4000, 4100), "ok"),
])
def test_volume_against_the_median_of_previous_scans(counts, expected):
    assert status(checks.check_volume(scans(*counts), DAY), "volume:ba") == expected


def test_volume_uses_only_the_last_seven_scans():
    # Ten old scans at 1,000 would make 4,000 a jump; the last seven are all ~4,000.
    rows = scans(*([1000] * 3 + [4000] * 7 + [4100]))
    assert status(checks.check_volume(rows, DAY), "volume:ba") == "ok"


def test_optional_source_only_warns():
    rows = scans(4000, 4100, 4200) + scans(700, 690, 100, source="arbeitnow")
    results = checks.check_volume(rows, DAY)
    assert status(results, "volume:arbeitnow") == "warn"
    assert status(results, "volume:ba") == "ok"


def test_first_scan_of_a_source_passes():
    assert status(checks.check_volume(scans(4000), DAY), "volume:ba") == "ok"


def test_missing_scan_for_today_fails():
    rows = [{"date": "2026-10-09", "source": "ba", "postings": "4000"}]
    assert status(checks.check_volume(rows, DAY), "volume") == "fail"


# --- Fields -----------------------------------------------------------------------------------

def listing(i, **kw):
    row = {"referenznummer": f"r{i}", "stellenangebotsTitel": "Werkstudent", "firma": "Acme",
           "stellenlokationen": [{"ort": "Berlin"}], "datumErsteVeroeffentlichung": "2026-10-01"}
    row.update(kw)
    return row


def test_complete_listings_pass():
    assert status(checks.check_fields([listing(i) for i in range(100)]), "fields") == "ok"


def test_a_listing_without_reference_number_fails():
    rows = [listing(i) for i in range(99)] + [listing(99, referenznummer=None)]
    assert status(checks.check_fields(rows), "fields") == "fail"


def test_a_field_missing_in_more_than_two_percent_fails():
    # A renamed field: the title is gone from 3 of 100 listings.
    rows = [listing(i) for i in range(97)] + [listing(i, stellenangebotsTitel="") for i in range(97, 100)]
    result = checks.check_fields(rows)
    assert status(result, "fields") == "fail"
    assert "title (3 of 100)" in result[0].detail


def test_a_few_missing_employers_are_fine():
    rows = [listing(i) for i in range(99)] + [listing(99, firma=None)]
    assert status(checks.check_fields(rows), "fields") == "ok"


def test_no_listings_fail():
    assert status(checks.check_fields([]), "fields") == "fail"


# --- Pay -----------------------------------------------------------------------------------------

def job(refnr, pay_min="", pay_max="", last_seen=DAY):
    return {"refnr": refnr, "pay_min": str(pay_min), "pay_max": str(pay_max), "last_seen": last_seen}


def test_rates_in_range_pass():
    assert status(checks.check_pay([job("a", 14, 16), job("b", 13.9, 13.9), job("c")], DAY), "pay") == "ok"


@pytest.mark.parametrize("lo, hi", [(8.5, 8.5), (15, 75), (1200, 1200), (18, 16)])
def test_rates_outside_range_or_reversed_fail(lo, hi):
    result = checks.check_pay([job("a", 15, 16), job("bad", lo, hi)], DAY)
    assert status(result, "pay") == "fail"
    assert "bad" in result[0].detail


def test_only_todays_postings_are_checked():
    assert status(checks.check_pay([job("old", 1200, 1200, last_seen="2026-10-01")], DAY), "pay") == "ok"


# --- Whole run --------------------------------------------------------------------------------------

def test_run_and_report():
    day, results = checks.run_checks([job("a", 15, 16)], scans(4000, 4100), [listing(1)])
    assert day == DAY
    assert {r.status for r in results} == {"ok"}
    text = checks.report(day, results)
    assert text.startswith(f"### Data checks for {DAY}") and "| pay | ✅ ok |" in text
