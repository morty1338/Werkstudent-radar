// Bootstrap 95% confidence interval for a median, computed in the browser for
// whatever the filters select. Same method as radar/stats.py: 2000 resamples
// with a fixed seed, percentile interval. (The random generators differ, so the
// last cent can differ from the server's figures.)

const RESAMPLES = 2000;
const SEED = 42;
const cache = new Map();

// Small seeded generator (mulberry32): the same selection always gives the same interval.
function mulberry32(seed) {
  let a = seed;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function quantile(sorted, q) {
  const pos = (sorted.length - 1) * q;
  const lo = Math.floor(pos);
  const hi = Math.min(lo + 1, sorted.length - 1);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo);
}

// sorted: values in ascending order. Returns [lo, hi] or null.
// A resample is drawn as a count per position, so its median is found with a
// running sum over the sorted values instead of sorting each resample.
export function medianCI(sorted, level = 0.95) {
  const n = sorted.length;
  if (!n) return null;
  const key = `${level}|${sorted.join(",")}`;
  if (cache.has(key)) return cache.get(key);
  const rand = mulberry32(SEED);
  const counts = new Uint32Array(n);
  const medians = new Float64Array(RESAMPLES);
  const k1 = (n - 1) >> 1; // 0-based ranks of the middle value(s)
  const k2 = n >> 1;
  for (let b = 0; b < RESAMPLES; b++) {
    counts.fill(0);
    for (let i = 0; i < n; i++) counts[(rand() * n) | 0]++;
    let seen = 0;
    let first = null;
    for (let i = 0; i < n; i++) {
      seen += counts[i];
      if (first === null && seen > k1) first = sorted[i];
      if (seen > k2) {
        medians[b] = (first + sorted[i]) / 2;
        break;
      }
    }
  }
  medians.sort();
  const tail = (1 - level) / 2;
  const out = [Math.round(quantile(medians, tail) * 100) / 100, Math.round(quantile(medians, 1 - tail) * 100) / 100];
  if (cache.size > 500) cache.clear();
  cache.set(key, out);
  return out;
}
