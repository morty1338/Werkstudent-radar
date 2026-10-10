"""The UI dictionary (docs/assets/i18n.js): complete in both languages, and every
key the page uses exists."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

DOCS = Path(__file__).resolve().parent.parent / "docs"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


@pytest.fixture(scope="module")
def dictionary(tmp_path_factory):
    script = tmp_path_factory.mktemp("i18n") / "keys.mjs"
    script.write_text(
        'globalThis.location = { search: "?lang=de" };\n'
        f"const m = await import({json.dumps((DOCS / 'assets' / 'i18n.js').as_uri())});\n"
        "console.log(JSON.stringify({ keys: m.KEYS, noEn: m.missingEnglish(), noDe: m.missingGerman(),"
        " sample: m.t('filter.show', { n: '4.822' }), plural: m.t('tile.places', { n: 1, v: '1' }) }));\n"
    )
    out = subprocess.run(["node", str(script)], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def test_every_entry_has_both_languages(dictionary):
    assert dictionary["noEn"] == []
    assert dictionary["noDe"] == []
    assert dictionary["sample"] == "4.822 Jobs anzeigen"
    assert dictionary["plural"] == "an 1 Ort"


def test_every_key_used_by_the_page_exists(dictionary):
    keys = set(dictionary["keys"])
    html = (DOCS / "index.html").read_text()
    used = set(re.findall(r'data-i18n(?:-html)?="([^"]+)"', html))
    used |= {pair.split(":")[1] for attrs in re.findall(r'data-i18n-attr="([^"]+)"', html) for pair in attrs.split(";")}
    for js in (DOCS / "assets").glob("*.js"):
        used |= set(re.findall(r'\bt\("([a-z_]+(?:\.[a-z_0-9]+)?)"', js.read_text()))
        # keys picked with a condition: t(x ? "a.b" : "c.d")
        used |= set(re.findall(r'\bt\([^()]*?\?\s*"([a-z_]+\.[a-z_0-9]+)"\s*:\s*"[a-z_]+\.[a-z_0-9]+"', js.read_text()))
        used |= set(re.findall(r'\bt\([^()]*?\?\s*"[a-z_]+\.[a-z_0-9]+"\s*:\s*"([a-z_]+\.[a-z_0-9]+)"', js.read_text()))
    assert used - keys == set()
    assert len(used) > 150
