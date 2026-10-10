"""Second source: parsing Arbeitnow postings and merging them with the Bundesagentur's."""

import pytest

from radar import arbeitnow
from radar.enrich import merge_arbeitnow, same_posting_key

GERMAN = {"Berlin": (52.52, 13.40), "München": (48.14, 11.58), "Hamburg": (53.55, 9.99)}


def job(slug, title="Werkstudent Data Analytics (m/w/d)", company="Start-up GmbH", location="Berlin",
        description="<p>Du hast Kenntnisse in <strong>SQL</strong> und Python.</p>", job_types=()):
    return {"slug": slug, "title": title, "company_name": company, "location": location,
            "description": description, "job_types": list(job_types), "remote": False,
            "url": f"https://www.arbeitnow.com/jobs/{slug}", "created_at": 1791590400}


def test_html_to_text_keeps_list_items_apart():
    text = arbeitnow.html_to_text("<p>Profil</p><ul><li>SQL</li><li>Python &amp; R</li></ul>")
    assert text.splitlines() == ["Profil", "• SQL", "• Python & R"]


def test_places():
    assert arbeitnow.place("Berlin, Germany", GERMAN) == ("Berlin", False, True)
    assert arbeitnow.place("Munich", GERMAN) == ("München", False, True)
    assert arbeitnow.place("Hamburg Office", GERMAN) == ("Hamburg", False, True)
    assert arbeitnow.place("Remote", GERMAN) == ("", True, True)
    assert arbeitnow.place("Homeoffice", GERMAN)[2] is True
    assert arbeitnow.place("London", GERMAN)[2] is False
    assert arbeitnow.place("Paris, France", GERMAN)[2] is False
    assert arbeitnow.place("Potsdam, Germany", GERMAN) == ("Potsdam", False, True)
    assert arbeitnow.place("Zürich, Switzerland", GERMAN)[2] is False
    assert arbeitnow.place("Wien", GERMAN)[2] is False


@pytest.mark.parametrize("location,city", [
    ("Hanover", "Hannover"),
    ("Gräfelfing/Munich", "München"),
    ("Berlin (Zentrale)", "Berlin"),
    ("Berlin Fasanenstrasse", "Berlin"),
    ("Cybay Hannover", "Hannover"),
    ("Köln Zentrale", "Köln"),
    ("Hamburg (HH)", "Hamburg"),
    ("Berlin oder Mainz", "Berlin"),
    ("Berlin | Global Team", "Berlin"),
    ("Hamburg Filiale", "Hamburg"),
    ("Nagold", "Nagold"),
    ("Ottobrunn, Bavaria", "Ottobrunn"),
])
def test_german_places_in_many_shapes(location, city):
    places = {**GERMAN, "Hannover": (52.37, 9.73), "Köln": (50.94, 6.96), "Mainz": (50.0, 8.27)}
    assert arbeitnow.place(location, places) == (city, False, True)


def test_werkstudent_by_title_or_type():
    assert arbeitnow.is_werkstudent_job(job("a"))
    assert arbeitnow.is_werkstudent_job(job("b", title="Data Analyst", job_types=["Working student", "Part time"]))
    assert not arbeitnow.is_werkstudent_job(job("c", title="Data Analyst", job_types=["Full Time"]))
    assert arbeitnow.is_werkstudent_job(job("d", title="Werksstudent PR & Marketing (m/w/d)"))
    assert not arbeitnow.is_werkstudent_job(job("e", title="Studentische Hilfskraft", job_types=["Werkstudent"]))
    assert not arbeitnow.is_werkstudent_job(job("f", title="Abschluss- oder Projektarbeit im Bereich KI", job_types=["Working student"]))


@pytest.mark.parametrize("a, b, same", [
    (("Acme GmbH", "Werkstudent (m/w/d) Data"), ("ACME GmbH", "Werkstudent Data (w/m/d)"), True),
    (("Acme GmbH", "Werkstudent – Data"), ("Acme GmbH", "Werkstudent Data"), True),
    (("Acme GmbH", "Werkstudent Data"), ("Acme AG", "Werkstudent Data"), False),
    (("Acme GmbH", "Werkstudent Vertrieb"), ("Acme GmbH", "Werkstudent Marketing"), False),
])
def test_same_posting_key_ignores_case_gender_tags_and_punctuation(a, b, same):
    assert (same_posting_key(*a) == same_posting_key(*b)) is same


def test_merge_adds_tags_and_skips_duplicates_and_abroad():
    jobs = {}
    ba_keys = {same_posting_key("Big Corp AG", "Werkstudent Controlling (m/w/d)")}
    an = [
        job("new"),
        job("dup", title="Werkstudent Controlling (w/m/d)", company="Big Corp AG"),
        job("uk", location="London"),
    ]
    stats = merge_arbeitnow(jobs, "2026-10-11", an, True, ba_keys, GERMAN)
    assert stats == {"kept": 1, "not_werkstudent": 0, "duplicates": 1, "abroad": 1, "carried": 0}
    row = jobs["an:new"]
    assert row["source"] == "arbeitnow" and row["url"].endswith("/new")
    assert (row["lat"], row["lon"]) == GERMAN["Berlin"]
    assert {"sql", "python"} <= set(row["skills"].split("|"))
    assert row["first_seen"] == row["last_seen"] == "2026-10-11"


def test_incomplete_crawl_keeps_recent_postings():
    jobs = {
        "an:recent": {"refnr": "an:recent", "source": "arbeitnow", "last_seen": "2026-10-10"},
        "an:old": {"refnr": "an:old", "source": "arbeitnow", "last_seen": "2026-10-01"},
        "ba1": {"refnr": "ba1", "source": "ba", "last_seen": "2026-10-10"},
    }
    stats = merge_arbeitnow(jobs, "2026-10-11", [], False, set(), GERMAN)
    assert stats["carried"] == 1
    assert jobs["an:recent"]["last_seen"] == "2026-10-11"
    assert jobs["an:old"]["last_seen"] == "2026-10-01"
    assert jobs["ba1"]["last_seen"] == "2026-10-10"  # only the second source is carried forward


def test_complete_crawl_drops_postings_that_are_gone():
    jobs = {"an:gone": {"refnr": "an:gone", "source": "arbeitnow", "last_seen": "2026-10-10"}}
    merge_arbeitnow(jobs, "2026-10-11", [], True, set(), GERMAN)
    assert jobs["an:gone"]["last_seen"] == "2026-10-10"
