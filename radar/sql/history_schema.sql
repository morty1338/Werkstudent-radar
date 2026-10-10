-- data/history.sqlite: every posting ever seen and when it was online.
-- Rebuilt by radar/history.py from data/jobs.csv (posting attributes) and the
-- committed text tables data/history/scans.csv and data/history/online.csv.

-- One row per collection day and source.
CREATE TABLE scans (
    date      TEXT NOT NULL,          -- collection day, YYYY-MM-DD (Europe/Berlin)
    source    TEXT NOT NULL,          -- ba (Bundesagentur) | arbeitnow (company career sites)
    postings  INTEGER NOT NULL,       -- postings from this source online that day
    PRIMARY KEY (date, source)
);

-- Stretches of consecutive scans in which a posting was online. end_date is NULL
-- while the posting is still online at the latest scan; when it is missing from a
-- scan, its interval is closed at the scan before. A posting that comes back
-- gets a new interval.
CREATE TABLE online (
    refnr       TEXT NOT NULL,
    start_date  TEXT NOT NULL,
    end_date    TEXT,
    PRIMARY KEY (refnr, start_date)
);
CREATE INDEX online_open ON online (end_date);

-- One row per posting, upserted from data/jobs.csv. No job texts.
CREATE TABLE postings (
    refnr            TEXT PRIMARY KEY,
    source           TEXT NOT NULL,
    company          TEXT,
    first_seen       TEXT NOT NULL,
    last_seen        TEXT NOT NULL,   -- kept when the posting is missing from later scans
    field            TEXT,            -- category id, e.g. it, marketing
    city             TEXT,
    lat              REAL,
    lon              REAL,
    pay              REAL,            -- €/h, midpoint of the stated range; NULL if not stated
    german           TEXT,            -- required | implicit | plus | none | '' (no text)
    german_required  INTEGER          -- 1 required or implied, 0 not needed, NULL unknown
);

CREATE TABLE posting_skills (
    refnr  TEXT NOT NULL,
    skill  TEXT NOT NULL,
    PRIMARY KEY (refnr, skill)
);

-- Days between first and last sighting, and whether the posting is still online
-- (censored, for survival analysis).
CREATE VIEW lifetimes AS
SELECT p.refnr, p.source, p.field, p.first_seen, p.last_seen,
       CAST(julianday(p.last_seen) - julianday(p.first_seen) AS INTEGER) + 1 AS days_seen,
       p.last_seen = (SELECT MAX(date) FROM scans) AS still_online
FROM postings p;
