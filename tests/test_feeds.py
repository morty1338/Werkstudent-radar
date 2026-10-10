"""RSS feeds of new postings: which postings count as new, and what an item may contain."""

import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from radar import build, feeds
from tests.test_build import job, write_csv

TODAY = "2026-10-09"
LABELS = {"it": "IT & Software", "marketing": "Marketing & Communication"}


def feed(tmp_path, rows):
    path = tmp_path / "jobs.csv"
    write_csv(path, rows)
    out = tmp_path / "feeds"
    counts = feeds.write_feeds(build.load_db(path), LABELS, feed_dir=out, built=datetime(2026, 10, 9, 5, tzinfo=timezone.utc))
    return counts, {name: ET.parse(out / f"{name}.xml").getroot() for name in counts}


def items(root):
    return [{child.tag: (child.text or "") for child in item} for item in root.iter("item")]


def base_rows(*extra):
    # "start" sets the first collection day (2026-10-01): it isn't new.
    return [job("start", first_seen="2026-10-01", published="2026-09-01", last_seen=TODAY), *extra]


def test_new_postings_newest_first_with_link_and_facts(tmp_path):
    counts, roots = feed(tmp_path, base_rows(
        job("a", title="Werkstudent Data & BI <SQL>", company="Acme", city="Köln", first_seen="2026-10-08",
            published="2026-10-07", pay_min=16, pay_max=18, german="none"),
        job("b", first_seen=TODAY, published=TODAY, category="marketing"),
    ))
    assert counts == {"all": 2, "it": 1, "marketing": 1}
    a, b = items(roots["all"])[1], items(roots["all"])[0]          # newest first
    assert b["guid"] == "b"
    assert a["title"] == "Werkstudent Data & BI <SQL>"              # escaped in XML, intact when parsed
    assert a["link"] == "https://www.arbeitsagentur.de/jobsuche/jobdetail/a"
    assert a["description"] == "Acme · Köln · €17.00/h · IT & Software · no German needed"
    assert a["pubDate"] == "Thu, 08 Oct 2026 06:30:00 +0200"


def test_old_gone_first_day_and_relisted_postings_are_not_new(tmp_path):
    counts, _ = feed(tmp_path, base_rows(
        job("week_old", first_seen="2026-10-02", published="2026-10-02"),     # 7 days ago: outside the window
        job("gone", first_seen="2026-10-08", published="2026-10-08", last_seen="2026-10-08"),
        job("relisted", first_seen="2026-10-08", published="2026-06-01"),     # published months before
        job("first_day", first_seen="2026-10-01", published="2026-10-01"),
        job("ok", first_seen="2026-10-08", published=""),                     # no date: kept
    ))
    assert counts["all"] == 1


def test_a_new_source_s_first_day_is_not_new(tmp_path):
    counts, _ = feed(tmp_path, base_rows(
        job("an:x", source="arbeitnow", first_seen=TODAY, published=TODAY, url="https://www.arbeitnow.com/jobs/x"),
        job("an:y", source="arbeitnow", first_seen="2026-10-08", published="2026-10-08", url="https://www.arbeitnow.com/jobs/y"),
    ))
    # an:y was found on Arbeitnow's first collection day; an:x a day later.
    assert counts["all"] == 1


def test_items_hold_no_job_text_and_channels_are_valid(tmp_path):
    _, roots = feed(tmp_path, base_rows(job("a", first_seen=TODAY, published=TODAY)))
    for name, root in roots.items():
        channel = root.find("channel")
        assert root.tag == "rss" and root.get("version") == "2.0"
        assert channel.find("link").text == feeds.SITE_URL
        self_link = channel.find("{http://www.w3.org/2005/Atom}link").get("href")
        assert self_link == f"{feeds.SITE_URL}feeds/{name}.xml"
        for item in root.iter("item"):
            assert set(child.tag for child in item) == {"title", "link", "guid", "pubDate", "category", "description"}
