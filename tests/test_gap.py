"""The skill-gap plan in docs/assets/gap.js (run with Node)."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

GAP_JS = (Path(__file__).resolve().parent.parent / "docs" / "assets" / "gap.js").as_uri()

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def run(tmp_path, call):
    script = tmp_path / "gap.mjs"
    script.write_text(f"import {{ fits, gapPlan }} from {json.dumps(GAP_JS)};\nconsole.log(JSON.stringify({call}));\n")
    return json.loads(subprocess.run(["node", str(script)], capture_output=True, text=True, check=True).stdout)


def test_fits_allows_one_gap_in_four(tmp_path):
    calls = "[fits([1,2,3], new Set([1,2])), fits([1,2,3,4], new Set([1,2,3])), fits([1,2,3,4], new Set([1,2])), fits([1,2,3,4,5,6,7,8], new Set([1,2,3,4,5,6]))]"
    assert run(tmp_path, calls) == [False, True, False, True]


def test_greedy_plan_counts_marginal_gains(tmp_path):
    # Skills: 0 SQL (have), 1 Python, 2 Power BI, 3 Excel.
    jobs = [[0, 1], [0, 1], [0, 1], [1, 2], [0, 2], [0, 2], [3], [0, 1, 2]]
    plan = run(tmp_path, f"gapPlan({json.dumps(jobs)}, new Set([0]), {{ steps: 3 }})")
    # Python first: completes [0,1]×3 (+3). Then Power BI completes [1,2], [0,2]×2 and
    # [0,1,2] (+4). Then Excel (+1).
    assert plan == [{"skill": 1, "gain": 3, "total": 3}, {"skill": 2, "gain": 4, "total": 7}, {"skill": 3, "gain": 1, "total": 8}]


def test_ties_go_to_the_more_demanded_skill(tmp_path):
    plan = run(tmp_path, "gapPlan([[5], [7]], new Set(), { steps: 1, demand: { 5: 10, 7: 99 } })")
    assert plan == [{"skill": 7, "gain": 1, "total": 1}]


def test_nothing_to_learn(tmp_path):
    assert run(tmp_path, "gapPlan([[1], [1, 2, 3, 4]], new Set([1, 2, 3, 4]))") == []
