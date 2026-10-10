-- In-memory schema for the aggregation step. jobs.csv is loaded into `jobs`;
-- the pipe-separated skills/majors columns are split into link tables.

CREATE TABLE jobs (
    refnr       TEXT PRIMARY KEY,
    title       TEXT,
    company     TEXT,
    city        TEXT,
    region      TEXT,
    lat         REAL,
    lon         REAL,
    category    TEXT,
    lang        TEXT,
    german      TEXT,             -- required | plus | none | implicit | '' (no text)
    english     INTEGER,
    pay_min     REAL,
    pay_max     REAL,
    pay         REAL,             -- midpoint of pay_min/pay_max, NULL if unknown
    pay_src     TEXT,
    hours       INTEGER,
    remote      INTEGER,
    external    INTEGER,
    published   TEXT,
    first_seen  TEXT,
    last_seen   TEXT,
    detail_ok   INTEGER
);

CREATE TABLE job_skills (refnr TEXT, skill TEXT, PRIMARY KEY (refnr, skill));
CREATE TABLE job_majors (refnr TEXT, major TEXT, PRIMARY KEY (refnr, major));

-- Dimension tables with display labels (filled from skills.py / extract.py).
CREATE TABLE skills     (id TEXT PRIMARY KEY, label TEXT, grp TEXT);
CREATE TABLE majors     (id TEXT PRIMARY KEY, label TEXT);
CREATE TABLE categories (id TEXT PRIMARY KEY, label TEXT);

-- Postings that were online on the latest collection day.
--
-- Some employers post the same role once per location (one company had 97
-- identical postings, all at minimum wage). Counting each copy would let them
-- dominate pay statistics, so pay is counted once per role:
--   role_pay  – pay of the first posting per (company, title), for national figures
--   city_pay  – pay of the first posting per (company, title, city), for city figures
-- Job counts still count every posting.
CREATE VIEW active AS
WITH ranked AS (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY company, LOWER(title) ORDER BY refnr)       AS role_n,
           ROW_NUMBER() OVER (PARTITION BY company, LOWER(title), city ORDER BY refnr) AS role_city_n
    FROM jobs
    WHERE last_seen = (SELECT MAX(last_seen) FROM jobs)
)
SELECT *,
       german IN ('none', 'plus')                AS no_german,   -- usable without German
       CASE WHEN role_n = 1 THEN pay END         AS role_pay,
       CASE WHEN role_city_n = 1 THEN pay END    AS city_pay
FROM ranked;

-- Jobs with a text: the denominator for anything extracted from the description.
CREATE VIEW active_tagged AS
SELECT * FROM active WHERE detail_ok = 1;
