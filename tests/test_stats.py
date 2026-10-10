"""Tests for the statistics helpers: bootstrap CIs and Kaplan–Meier with delayed entry."""

import json
import random
import shutil
import subprocess
from pathlib import Path

import pytest

from radar import stats

ROOT = Path(__file__).resolve().parent.parent


# --- Bootstrap CI of the median ------------------------------------------------------------

def test_ci_contains_the_median_and_is_reproducible():
    rng = random.Random(1)
    values = [round(rng.uniform(13, 22), 2) for _ in range(60)]
    lo, hi = stats.bootstrap_median_ci(values)
    median = stats.quantile(sorted(values), 0.5)
    assert lo <= median <= hi
    assert stats.bootstrap_median_ci(values) == (lo, hi)        # fixed seed


def test_identical_values_give_a_zero_width_interval():
    assert stats.bootstrap_median_ci([16.0] * 25) == (16.0, 16.0)


def test_interval_narrows_with_more_data():
    rng = random.Random(2)
    pool = [round(rng.uniform(13, 22), 2) for _ in range(2000)]
    width = lambda v: (lambda lo, hi: hi - lo)(*stats.bootstrap_median_ci(v))
    assert width(pool[:400]) < width(pool[:20])


def test_coverage_is_about_95_percent():
    # Draw many samples from a known distribution; ~95% of intervals should cover
    # its true median (15.5 for uniform 13–18). Small resample count keeps it fast.
    rng = random.Random(3)
    covered = 0
    for trial in range(200):
        sample = [rng.uniform(13, 18) for _ in range(40)]
        lo, hi = stats.bootstrap_median_ci(sample, resamples=400, seed=trial)
        covered += lo <= 15.5 <= hi
    assert 0.88 <= covered / 200 <= 0.99


def test_empty_input():
    assert stats.bootstrap_median_ci([]) == (None, None)


# --- Kaplan–Meier -------------------------------------------------------------------------------

def test_without_delayed_entry_it_matches_the_textbook_estimate():
    # Six subjects from day 0: events at 1, 2, 2, 4; censored at 3 and 5.
    obs = [(0, 1, True), (0, 2, True), (0, 2, True), (0, 3, False), (0, 4, True), (0, 5, False)]
    km = stats.kaplan_meier(obs, min_at_risk=1)
    curve = {t: s for t, s, *_ in km["curve"]}
    assert curve[1] == pytest.approx(5 / 6, abs=1e-4)
    assert curve[2] == pytest.approx(5 / 6 * 3 / 5, abs=1e-4)
    assert curve[4] == pytest.approx(5 / 6 * 3 / 5 * 1 / 2, abs=1e-4)
    assert km["median"] == 2                         # S(2) = 0.5


def test_delayed_entry_keeps_late_arrivals_out_of_early_risk_sets():
    # Two postings observed from day 0, one only from day 10 (published long before
    # the first scan). The early event's risk set must not include the late one.
    obs = [(0, 2, True), (0, 20, False), (10, 12, True)]
    km = stats.kaplan_meier(obs, min_at_risk=1)
    rows = {t: (s, n) for t, s, _, _, n in km["curve"]}
    assert rows[2] == (0.5, 2)                       # 1 of 2 at risk
    assert rows[12] == (pytest.approx(0.25), 2)      # 1 of 2 at risk (the late one and the censored one)


def test_curve_stops_where_too_few_are_at_risk():
    obs = [(0, t, True) for t in range(1, 41)]      # one event a day, 40 subjects
    km = stats.kaplan_meier(obs, min_at_risk=30)
    assert km["until"] == 11                         # 30 still at risk on day 11, 29 on day 12
    assert km["median"] is None


def test_confidence_band_brackets_the_estimate():
    obs = [(0, t, t % 3 != 0) for t in range(1, 200)]
    for t, s, lo, hi, _ in stats.kaplan_meier(obs, min_at_risk=10)["curve"]:
        assert lo <= s <= hi <= 1


# --- The browser's version (docs/assets/stats.js) ---------------------------------------------------

@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_browser_ci_agrees_with_python(tmp_path):
    rng = random.Random(4)
    samples = [sorted(round(rng.uniform(13, 22), 2) for _ in range(n)) for n in (10, 11, 57, 300)]
    samples.append([16.0] * 30)
    script = tmp_path / "ci.mjs"
    script.write_text(
        f"import {{ medianCI }} from {json.dumps((ROOT / 'docs/assets/stats.js').as_uri())};\n"
        "const samples = JSON.parse(process.argv[2]);\n"
        "console.log(JSON.stringify(samples.map((s) => [medianCI(s), medianCI(s)])));\n"
    )
    out = subprocess.run(["node", str(script), json.dumps(samples)], capture_output=True, text=True, check=True)
    for sample, (first, again) in zip(samples, json.loads(out.stdout)):
        assert first == again                                        # deterministic
        lo, hi = stats.bootstrap_median_ci(sample)
        median = stats.quantile(sample, 0.5)
        assert first[0] <= median <= first[1]
        # Different random generators: the ends agree up to resampling noise.
        tol = max(0.15, 0.25 * (hi - lo))
        assert abs(first[0] - lo) <= tol and abs(first[1] - hi) <= tol
