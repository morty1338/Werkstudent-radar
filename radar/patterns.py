"""Export the skill and study-programme rules for the browser.

The site analyses an uploaded CV in the browser with the same dictionary the
pipeline uses for job postings, so nobody's CV ever leaves their device. The
rules are Python regexes; JavaScript understands almost the same syntax except
for scoped flags like (?-i:Excel). Those patterns are exported as
case-sensitive regexes instead, which is what the scoped flag was for.
"""

from .extract import MAJORS
from .skills import SKILLS


def _strip_scoped_flags(pattern):
    """Turn every '(?-i:' group into a plain '(?:' group."""
    out, i = [], 0
    while i < len(pattern):
        if pattern.startswith("(?-i:", i):
            out.append("(?:")
            i += len("(?-i:")
        else:
            out.append(pattern[i])
            i += 1
    return "".join(out)


def to_js(pattern):
    """Return (source, flags) for JavaScript's RegExp."""
    if "(?-i:" in pattern:
        return _strip_scoped_flags(pattern), "u"
    return pattern, "iu"


def export(skill_ids):
    """Patterns for the given skills (the ones the site shows) and all study programmes."""
    wanted = set(skill_ids)
    return {
        "note": "Generated from radar/skills.py and radar/extract.py; see radar/patterns.py.",
        "skills": [
            {"id": sid, "patterns": [list(to_js(p)) for p in pats]}
            for sid, _, _, pats in SKILLS if sid in wanted
        ],
        "majors": [{"id": mid, "label": label, "patterns": [list(to_js(rx))]} for mid, label, rx in MAJORS],
    }
