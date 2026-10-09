-- Study programmes mentioned in postings.
WITH emp AS (
    SELECT jm.major, a.company, COUNT(*) AS n
    FROM active_tagged a JOIN job_majors jm ON jm.refnr = a.refnr
    WHERE a.role_pay IS NOT NULL
    GROUP BY jm.major, a.company
),
conc AS (
    SELECT major, COUNT(*) AS pay_employers, ROUND(1.0 * MAX(n) / SUM(n), 3) AS top_employer_share
    FROM emp GROUP BY major
)
SELECT m.id,
       m.label,
       COUNT(*)                                                        AS jobs,
       ROUND(1.0 * COUNT(*) / (SELECT COUNT(*) FROM active_tagged), 4) AS share,
       COUNT(a.role_pay)                                               AS with_pay,
       percentile(a.role_pay, 0.5)                                     AS median_pay,
       conc.pay_employers,
       conc.top_employer_share,
       ROUND(AVG(a.no_german), 4)                                      AS no_german_share
FROM job_majors jm
JOIN active_tagged a ON a.refnr = jm.refnr
JOIN majors m        ON m.id = jm.major
LEFT JOIN conc       ON conc.major = m.id
GROUP BY m.id
ORDER BY jobs DESC;
