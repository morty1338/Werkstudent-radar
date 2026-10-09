-- Most recently published postings per study programme (title + link only).
WITH ranked AS (
    SELECT jm.major, a.refnr, a.title, a.company, a.city, a.category, a.german, a.pay, a.published,
           ROW_NUMBER() OVER (PARTITION BY jm.major ORDER BY a.published DESC, a.refnr) AS rn
    FROM job_majors jm
    JOIN active_tagged a ON a.refnr = jm.refnr
)
SELECT * FROM ranked WHERE rn <= :n ORDER BY major, rn;
