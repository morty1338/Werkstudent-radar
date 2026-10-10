-- Per collection day: postings online, new (never seen before), back (online
-- again after a gap) and gone (online at the scan before, missing now).
-- The first scan has no "before", so its flows are NULL.
WITH days AS (
    SELECT date, SUM(postings) AS online, LAG(date) OVER (ORDER BY date) AS prev
    FROM scans
    GROUP BY date
),
firsts AS (
    SELECT refnr, MIN(start_date) AS first FROM online GROUP BY refnr
)
SELECT d.date,
       d.online,
       CASE WHEN d.prev IS NOT NULL THEN (SELECT COUNT(*) FROM firsts f WHERE f.first = d.date) END AS new,
       CASE WHEN d.prev IS NOT NULL THEN (
           SELECT COUNT(*) FROM online o JOIN firsts f USING (refnr)
           WHERE o.start_date = d.date AND f.first < d.date) END AS back,
       CASE WHEN d.prev IS NOT NULL THEN (SELECT COUNT(*) FROM online o WHERE o.end_date = d.prev) END AS gone
FROM days d
ORDER BY d.date;
