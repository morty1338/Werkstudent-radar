-- One row per tagged posting for the in-browser skill checker. The order (by
-- reference number) is shared by checker.json and postings.json, which are
-- matched up by position.
SELECT a.refnr, a.title, a.company, a.city, a.published,
       a.category, a.german, a.pay,
       GROUP_CONCAT(js.skill, '|') AS skills
FROM active_tagged a
LEFT JOIN job_skills js ON js.refnr = a.refnr
GROUP BY a.refnr
ORDER BY a.refnr;
