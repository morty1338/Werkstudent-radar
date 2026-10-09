-- Distribution of hourly pay in 1 € bins; everything from 25 € up is one bin.
SELECT MIN(CAST(role_pay AS INTEGER), 25) AS bin,
       COUNT(*)                     AS jobs
FROM active
WHERE role_pay IS NOT NULL
GROUP BY bin
ORDER BY bin;
