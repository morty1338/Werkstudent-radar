-- Today's metrics in long format, appended to data/history.csv.
-- Stored daily because a posting's state on a given day can't be rebuilt later.
WITH t AS (SELECT * FROM active)
-- The 95% CI of the median is kept for the total only (bootstrapping every row would be slow).
SELECT 'total' AS dim, 'all' AS key, COUNT(*) AS jobs, COUNT(role_pay) AS with_pay,
       percentile(role_pay, 0.5) AS median_pay, SUM(no_german) AS no_german,
       median_ci(role_pay, 0) AS median_pay_lo, median_ci(role_pay, 1) AS median_pay_hi
FROM t
UNION ALL
SELECT 'category', category, COUNT(*), COUNT(role_pay), percentile(role_pay, 0.5), SUM(no_german), NULL, NULL
FROM t GROUP BY category
UNION ALL
SELECT 'city', city, COUNT(*), COUNT(city_pay), percentile(city_pay, 0.5), SUM(no_german), NULL, NULL
FROM t WHERE city IN (SELECT city FROM t WHERE city <> '' GROUP BY city ORDER BY COUNT(*) DESC LIMIT :top_cities)
GROUP BY city
UNION ALL
SELECT 'skill', js.skill, COUNT(*), COUNT(t.role_pay), percentile(t.role_pay, 0.5), SUM(t.no_german), NULL, NULL
FROM t JOIN job_skills js ON js.refnr = t.refnr GROUP BY js.skill
UNION ALL
SELECT 'major', jm.major, COUNT(*), COUNT(t.role_pay), percentile(t.role_pay, 0.5), SUM(t.no_german), NULL, NULL
FROM t JOIN job_majors jm ON jm.refnr = t.refnr GROUP BY jm.major
UNION ALL
SELECT 'german', german, COUNT(*), COUNT(role_pay), percentile(role_pay, 0.5), SUM(no_german), NULL, NULL
FROM t WHERE detail_ok = 1 GROUP BY german
UNION ALL
SELECT 'source', source, COUNT(*), COUNT(role_pay), percentile(role_pay, 0.5), SUM(no_german), NULL, NULL
FROM t GROUP BY source;
