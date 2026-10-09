-- One row per tagged posting for the in-browser skill checker.
SELECT a.refnr, a.category, a.city, a.german, a.pay,
       GROUP_CONCAT(js.skill, '|') AS skills
FROM active_tagged a
LEFT JOIN job_skills js ON js.refnr = a.refnr
GROUP BY a.refnr
ORDER BY a.refnr;
