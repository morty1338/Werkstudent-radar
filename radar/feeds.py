"""RSS feeds of new Werkstudent postings, rebuilt every day by radar.build.

    docs/feeds/all.xml        postings first seen in the last 7 days, newest first
    docs/feeds/<field>.xml    the same for one field (it.xml, marketing.xml, …)

Each item has the posting's title, employer, city, hourly pay and field, and
links to the original posting. Job texts belong to the employers and are not
included. Feed URLs stay fixed (no version suffix), so subscriptions keep working.
"""

import os
from datetime import date, datetime, time, timezone
from email.utils import format_datetime
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEED_DIR = os.path.join(ROOT, "docs", "feeds")
SITE_URL = "https://morty1338.github.io/werkstudent-radar/"
JOB_URL = "https://www.arbeitsagentur.de/jobsuche/jobdetail/{refnr}"
DAYS = 7
MAX_ITEMS_ALL = 300
MAX_ITEMS_FIELD = 100
BERLIN = ZoneInfo("Europe/Berlin")
SCAN_TIME = time(6, 30)  # the daily collection runs in the early morning (Berlin)


def new_postings(db):
    """Postings first seen in the last DAYS days that are still online, newest first.

    "New" means new on the market, not just new to us: postings found on a source's
    first collection day were there before, and a posting also needs a publication
    date at most DAYS days before it was first seen (else it was only re-listed).
    """
    return [dict(r) for r in db.execute("""
        SELECT refnr, title, company, city, category, pay, german, source, url, first_seen
        FROM active
        WHERE first_seen > DATE((SELECT MAX(last_seen) FROM jobs), :back)
          AND first_seen > (SELECT MIN(j.first_seen) FROM jobs j WHERE j.source = active.source)
          AND (published = '' OR SUBSTR(published, 1, 10) >= DATE(first_seen, :back))
        ORDER BY first_seen DESC, refnr
    """, {"back": f"-{DAYS} days"})]


def _rfc822(day):
    return format_datetime(datetime.combine(date.fromisoformat(day), SCAN_TIME, BERLIN))


def _item(p, field_label):
    link = p["url"] or JOB_URL.format(refnr=p["refnr"])
    facts = [p["company"], p["city"], f"€{p['pay']:.2f}/h" if p["pay"] is not None else None, field_label,
             "no German needed" if p["german"] in ("none", "plus") else None]
    return (
        "    <item>\n"
        f"      <title>{escape(p['title'])}</title>\n"
        f"      <link>{escape(link)}</link>\n"
        f"      <guid isPermaLink=\"false\">{escape(p['refnr'])}</guid>\n"
        f"      <pubDate>{_rfc822(p['first_seen'])}</pubDate>\n"
        f"      <category>{escape(field_label)}</category>\n"
        f"      <description>{escape(' · '.join(f for f in facts if f))}</description>\n"
        "    </item>\n"
    )


def render(postings, labels, *, name, title, built):
    """One RSS 2.0 document. labels: field id -> display label."""
    self_url = f"{SITE_URL}feeds/{name}.xml"
    items = "".join(_item(p, labels.get(p["category"], "Other")) for p in postings)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n'
        "  <channel>\n"
        f"    <title>{escape(title)}</title>\n"
        f"    <link>{SITE_URL}</link>\n"
        f"    <atom:link href=\"{self_url}\" rel=\"self\" type=\"application/rss+xml\"/>\n"
        "    <description>New Werkstudent postings in Germany from the Bundesagentur für Arbeit and company "
        "career sites, collected daily by Werkstudent Radar. Links lead to the original postings.</description>\n"
        "    <language>en</language>\n"
        f"    <lastBuildDate>{format_datetime(built)}</lastBuildDate>\n"
        "    <ttl>720</ttl>\n"
        f"{items}"
        "  </channel>\n"
        "</rss>\n"
    )


def write_feeds(db, labels, feed_dir=FEED_DIR, built=None):
    """Write all.xml and one feed per field; returns {name: item count}."""
    built = built or datetime.now(timezone.utc)
    postings = new_postings(db)
    os.makedirs(feed_dir, exist_ok=True)
    feeds = {"all": (postings[:MAX_ITEMS_ALL], "Werkstudent Radar: new Werkstudent jobs in Germany")}
    for field, label in labels.items():
        mine = [p for p in postings if p["category"] == field][:MAX_ITEMS_FIELD]
        feeds[field] = (mine, f"Werkstudent Radar: new Werkstudent jobs in {label}")
    counts = {}
    for name, (items, title) in feeds.items():
        with open(os.path.join(feed_dir, f"{name}.xml"), "w", encoding="utf-8") as f:
            f.write(render(items, labels, name=name, title=title, built=built))
        counts[name] = len(items)
    return counts
