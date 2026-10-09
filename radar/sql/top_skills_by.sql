-- Top :n skills within each job field (window function picks the top rows per group).
WITH counts AS (
    SELECT a.category AS grp, js.skill, COUNT(*) AS jobs
    FROM active_tagged a
    JOIN job_skills js ON js.refnr = a.refnr
    GROUP BY a.category, js.skill
),
ranked AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY grp ORDER BY jobs DESC, skill) AS rn
    FROM counts
)
SELECT grp, skill, jobs FROM ranked WHERE rn <= :n ORDER BY grp, rn;
