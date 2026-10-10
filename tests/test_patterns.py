"""The browser must find the same skills in a CV as the Python rules do."""

import json
import re
import shutil
import subprocess

import pytest

from radar import patterns
from radar.extract import find_majors, find_skills
from radar.skills import SKILLS

CV = """
Ivan Example – B.Sc. Wirtschaftsinformatik, TU Berlin
Werkstudent Data Analytics: Datenanalyse mit Python (pandas) und SQL, Dashboards in Power BI.
Kenntnisse: MS Office (Excel, PowerPoint), SAP S/4HANA Grundlagen, Git, Jira, Scrum.
Languages: German (C1), English (fluent). Führerschein Klasse B.
Interests: React and TypeScript side projects, Docker.
"""


def test_scoped_flags_become_case_sensitive():
    assert patterns.to_js(r"(?-i:\bExcel\b|\bEXCEL\b)") == (r"(?:\bExcel\b|\bEXCEL\b)", "u")
    assert patterns.to_js(r"\bsql\b") == (r"\bsql\b", "iu")


def test_export_contains_requested_skills_only():
    data = patterns.export(["sql", "excel"])
    assert [s["id"] for s in data["skills"]] == ["sql", "excel"]
    assert {m["id"] for m in data["majors"]} >= {"wiinf", "inf", "bwl", "wiing"}


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_javascript_finds_the_same_skills(tmp_path):
    data = patterns.export([sid for sid, *_ in SKILLS])
    script = tmp_path / "check.mjs"
    script.write_text(
        "const data = JSON.parse(process.argv[2]); const text = process.argv[3];\n"
        "const hit = (list) => list.filter((s) => s.patterns.some(([src, f]) => new RegExp(src, f).test(text))).map((s) => s.id);\n"
        "console.log(JSON.stringify({ skills: hit(data.skills).sort(), majors: hit(data.majors).sort() }));\n"
    )
    out = subprocess.run(["node", str(script), json.dumps(data), CV], capture_output=True, text=True, check=True)
    js = json.loads(out.stdout)
    assert js["skills"] == sorted(find_skills(CV, require_context=False))
    assert js["majors"] == sorted(find_majors(CV))
    assert {"python", "sql", "powerbi", "excel", "sap", "git", "driving_licence"} <= set(js["skills"])


def test_every_exported_pattern_is_valid_python_too():
    for skill in patterns.export([sid for sid, *_ in SKILLS])["skills"]:
        for src, flags in skill["patterns"]:
            re.compile(src, re.IGNORECASE if "i" in flags else 0)
