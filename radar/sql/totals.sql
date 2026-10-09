-- Headline numbers for the latest day. Pay figures count each role once (see schema.sql).
SELECT
    (SELECT MAX(last_seen) FROM jobs)                                    AS as_of,
    COUNT(*)                                                             AS jobs,
    SUM(published >= DATE((SELECT MAX(last_seen) FROM jobs), '-6 days')) AS published_7d,
    COUNT(pay)                                                           AS postings_with_pay,
    COUNT(role_pay)                                                      AS with_pay,
    percentile(role_pay, 0.5)                                            AS median_pay,
    percentile(role_pay, 0.25)                                           AS p25_pay,
    percentile(role_pay, 0.75)                                           AS p75_pay,
    SUM(detail_ok)                                                       AS tagged,
    SUM(no_german)                                                       AS no_german,
    SUM(lang = 'en')                                                     AS english_postings,
    SUM(remote)                                                          AS remote,
    COUNT(hours)                                                         AS with_hours,
    percentile(hours, 0.5)                                               AS median_hours,
    COUNT(DISTINCT company)                                              AS companies,
    COUNT(DISTINCT city)                                                 AS cities
FROM active;
