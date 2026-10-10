"""Statistics used by the build step: bootstrap confidence intervals for medians
and Kaplan–Meier survival curves for how long postings stay online.

Plain Python, no dependencies; fast enough for a few hundred groups a day.
"""

import math
import random
from bisect import bisect_left

BOOTSTRAP_RESAMPLES = 2000
BOOTSTRAP_SEED = 42      # fixed, so the same data always gives the same interval
CI_LEVEL = 0.95


def quantile(sorted_values, q):
    """Linear interpolation between closest ranks (same as the SQL percentile() and the site)."""
    if not sorted_values:
        return None
    pos = (len(sorted_values) - 1) * q
    lo = math.floor(pos)
    hi = min(lo + 1, len(sorted_values) - 1)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (pos - lo)


def bootstrap_median_ci(values, resamples=BOOTSTRAP_RESAMPLES, level=CI_LEVEL, seed=BOOTSTRAP_SEED):
    """Percentile-bootstrap confidence interval for the median: resample the values
    with replacement, take each resample's median, and report the middle `level`
    of those medians. Returns (lo, hi), or (None, None) for no values.

    The values are sorted once; a resample is a sorted list of indices into them,
    so its median can be read off without sorting values again.
    """
    n = len(values)
    if not n:
        return None, None
    s = sorted(values)
    rng = random.Random(seed)
    idx = range(n)
    mid = n // 2
    medians = []
    for _ in range(resamples):
        pick = sorted(rng.choices(idx, k=n))
        medians.append(s[pick[mid]] if n % 2 else (s[pick[mid - 1]] + s[pick[mid]]) / 2)
    medians.sort()
    tail = (1 - level) / 2
    return round(quantile(medians, tail), 2), round(quantile(medians, 1 - tail), 2)


def kaplan_meier(observations, min_at_risk=30, z=1.96):
    """Kaplan–Meier survival estimate with delayed entry (left truncation).

    observations: (entry, exit, event) per subject, in days since it started.
    A subject is at risk on the interval (entry, exit]: it is only observed from
    `entry` on (a posting published weeks before the first scan can't have been
    seen going offline earlier). event=True means it ended at `exit`; False means
    it was still going (censored).

    The curve stops before the first event time with fewer than `min_at_risk`
    subjects at risk, where single postings would swing it. Confidence bands use
    Greenwood's variance on the log scale.

    Returns {"curve": [(t, s, lo, hi, at_risk), …] starting at (0, 1, 1, 1, …),
             "median": first t with s ≤ 0.5 or None, "until": last t of the curve}.
    """
    entries = sorted(e for e, _, _ in observations)
    exits = sorted(x for _, x, _ in observations)
    deaths = {}
    for _, x, event in observations:
        if event:
            deaths[x] = deaths.get(x, 0) + 1

    s, var = 1.0, 0.0
    curve = [(0, 1.0, 1.0, 1.0, bisect_left(entries, 1) - bisect_left(exits, 1))]
    median = None
    for t in sorted(deaths):
        at_risk = bisect_left(entries, t) - bisect_left(exits, t)   # entry < t <= exit
        if at_risk < min_at_risk:
            break
        d = deaths[t]
        s *= 1 - d / at_risk
        if at_risk > d:
            var += d / (at_risk * (at_risk - d))
            spread = z * math.sqrt(var)
            lo, hi = s * math.exp(-spread), min(1.0, s * math.exp(spread))
        else:
            lo, hi = 0.0, 0.0
        curve.append((t, round(s, 4), round(lo, 4), round(hi, 4), at_risk))
        if median is None and s <= 0.5:
            median = t
    return {"curve": curve, "median": median, "until": curve[-1][0]}
