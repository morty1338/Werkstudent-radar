-- Job fields: size, pay and how many are open to non-German speakers.
-- pay_employers / top_employer_share show whether a median is driven by one employer.
WITH emp AS (
    SELECT category AS key, company, COUNT(*) AS n
    FROM active WHERE role_pay IS NOT NULL
    GROUP BY category, company
),
conc AS (
    SELECT key, COUNT(*) AS pay_employers, ROUND(1.0 * MAX(n) / SUM(n), 3) AS top_employer_share
    FROM emp GROUP BY key
)
SELECT c.id                              AS key,
       c.label,
       COUNT(a.refnr)                    AS jobs,
       COUNT(a.role_pay)                 AS with_pay,
       percentile(a.role_pay, 0.5)       AS median_pay,
       conc.pay_employers,
       conc.top_employer_share,
       ROUND(AVG(a.no_german), 4)        AS no_german_share,
       SUM(a.no_german)                  AS no_german
FROM categories c
JOIN active a      ON a.category = c.id
LEFT JOIN conc     ON conc.key = c.id
GROUP BY c.id
ORDER BY jobs DESC;
