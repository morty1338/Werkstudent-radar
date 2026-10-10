-- Skills asked for together, among today's postings with a text.
--   share  P(other | skill): of the postings asking for `skill`, the share also asking for `other`
--   lift   P(skill and other) / (P(skill) · P(other)): how much more often the two
--          appear together than if they were unrelated (1 = no relation)
-- Pairs need at least :min_pair postings; per skill the :top pairs with the highest lift.
WITH js AS (
    SELECT s.refnr, s.skill
    FROM job_skills s JOIN active_tagged a ON a.refnr = s.refnr
),
total AS (SELECT COUNT(*) AS n FROM active_tagged),
single AS (SELECT skill, COUNT(*) AS jobs FROM js GROUP BY skill),
pairs AS (
    SELECT a.skill, b.skill AS other, COUNT(*) AS together
    FROM js a JOIN js b ON b.refnr = a.refnr AND b.skill <> a.skill
    GROUP BY a.skill, b.skill
    HAVING COUNT(*) >= :min_pair
),
scored AS (
    SELECT p.skill, p.other, p.together,
           ROUND(1.0 * p.together / sa.jobs, 4)                            AS share,
           ROUND(1.0 * p.together * total.n / (sa.jobs * sb.jobs), 2)      AS lift
    FROM pairs p
    JOIN single sa ON sa.skill = p.skill
    JOIN single sb ON sb.skill = p.other
    CROSS JOIN total
),
ranked AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY skill ORDER BY lift DESC, together DESC, other) AS rank
    FROM scored
    WHERE lift > 1
)
SELECT skill, other, together, share, lift
FROM ranked
WHERE rank <= :top
ORDER BY skill, rank;
