-- How much German do postings ask for?
SELECT german AS key,
       COUNT(*) AS jobs,
       ROUND(1.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 4) AS share
FROM active_tagged
GROUP BY german
ORDER BY CASE german WHEN 'none' THEN 1 WHEN 'plus' THEN 2 WHEN 'implicit' THEN 3 ELSE 4 END;
