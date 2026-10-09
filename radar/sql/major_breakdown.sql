-- For each study programme: top :n job fields, skills and cities.
WITH base AS (
    SELECT jm.major, a.*
    FROM job_majors jm
    JOIN active_tagged a ON a.refnr = jm.refnr
),
parts AS (
    SELECT major, 'category' AS dim, category AS key, COUNT(*) AS jobs FROM base GROUP BY major, category
    UNION ALL
    SELECT major, 'city', city, COUNT(*) FROM base WHERE city <> '' GROUP BY major, city
    UNION ALL
    SELECT b.major, 'skill', js.skill, COUNT(*)
    FROM base b JOIN job_skills js ON js.refnr = b.refnr
    GROUP BY b.major, js.skill
),
ranked AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY major, dim ORDER BY jobs DESC, key) AS rn
    FROM parts
)
SELECT major, dim, key, jobs FROM ranked WHERE rn <= :n ORDER BY major, dim, rn;
