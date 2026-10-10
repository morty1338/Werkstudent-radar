// Skill gap: which skills to learn next to qualify for the most additional jobs.
// No imports and no DOM, so it can be tested in Node.
//
// A posting fits when you lack at most a quarter (rounded down) of the skills
// it lists (the same rule as match.js). The plan is greedy: each step adds the
// skill that makes the most postings fit on top of the skills you have and the
// ones picked before it. Greedy isn't guaranteed optimal for a set of skills,
// but it is for the first step and close to it after.

export function fits(skills, have) {
  let missing = 0;
  for (const s of skills) if (!have.has(s)) missing++;
  return missing <= Math.floor(skills.length / 4);
}

// jobs: arrays of skill indices (one per posting); have: Set of skill indices.
// demand: optional tie-break, skill index -> postings asking for it.
// Returns [{ skill, gain, total }] where total is the cumulative number of extra postings.
export function gapPlan(jobs, have, { steps = 3, demand = null } = {}) {
  const owned = new Set(have);
  let open = jobs.filter((skills) => skills.length && !fits(skills, owned));
  const plan = [];
  let total = 0;
  for (let k = 0; k < steps; k++) {
    // Only a posting one skill short can be completed by a single skill.
    const gains = new Map();
    for (const skills of open) {
      const missing = skills.filter((s) => !owned.has(s));
      if (missing.length === Math.floor(skills.length / 4) + 1) {
        for (const s of missing) gains.set(s, (gains.get(s) || 0) + 1);
      }
    }
    let best = null;
    for (const [s, g] of gains) {
      if (!best || g > best[1] || (g === best[1] && (demand?.[s] ?? 0) > (demand?.[best[0]] ?? 0)) ||
          (g === best[1] && (demand?.[s] ?? 0) === (demand?.[best[0]] ?? 0) && s < best[0])) best = [s, g];
    }
    if (!best) break;
    owned.add(best[0]);
    open = open.filter((skills) => !fits(skills, owned));
    total += best[1];
    plan.push({ skill: best[0], gain: best[1], total });
  }
  return plan;
}
