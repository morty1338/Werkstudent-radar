-- Cities with at least :min_jobs postings. Pay counts each role once per city.
WITH emp AS (
    SELECT city, company, COUNT(*) AS n
    FROM active WHERE city_pay IS NOT NULL
    GROUP BY city, company
),
conc AS (
    SELECT city, COUNT(*) AS pay_employers, ROUND(1.0 * MAX(n) / SUM(n), 3) AS top_employer_share
    FROM emp GROUP BY city
)
SELECT a.city,
       COUNT(*)                            AS jobs,
       COUNT(a.city_pay)                   AS with_pay,
       percentile(a.city_pay, 0.5)         AS median_pay,
       conc.pay_employers,
       conc.top_employer_share,
       ROUND(AVG(a.no_german), 4)          AS no_german_share,
       SUM(a.no_german)                    AS no_german,
       SUM(a.category IN ('it', 'data'))   AS it_data_jobs
FROM active a
LEFT JOIN conc ON conc.city = a.city
WHERE a.city <> ''
GROUP BY a.city
HAVING COUNT(*) >= :min_jobs
ORDER BY jobs DESC;
