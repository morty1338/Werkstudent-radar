-- Skill demand: share of tagged postings asking for it, and what those jobs pay.
WITH emp AS (
    SELECT js.skill, a.company, COUNT(*) AS n
    FROM active_tagged a JOIN job_skills js ON js.refnr = a.refnr
    WHERE a.role_pay IS NOT NULL
    GROUP BY js.skill, a.company
),
conc AS (
    SELECT skill, COUNT(*) AS pay_employers, ROUND(1.0 * MAX(n) / SUM(n), 3) AS top_employer_share
    FROM emp GROUP BY skill
)
SELECT s.id,
       s.label,
       s.grp                                                           AS "group",
       COUNT(*)                                                        AS jobs,
       ROUND(1.0 * COUNT(*) / (SELECT COUNT(*) FROM active_tagged), 4) AS share,
       COUNT(a.role_pay)                                               AS with_pay,
       percentile(a.role_pay, 0.5)                                     AS median_pay,
       conc.pay_employers,
       conc.top_employer_share,
       ROUND(AVG(a.no_german), 4)                                      AS no_german_share
FROM job_skills js
JOIN active_tagged a ON a.refnr = js.refnr
JOIN skills s        ON s.id = js.skill
LEFT JOIN conc       ON conc.skill = s.id
GROUP BY s.id
ORDER BY jobs DESC, s.id;
