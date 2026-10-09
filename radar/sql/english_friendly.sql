-- Every posting that can be done without German, newest first.
SELECT refnr, title, company, city, category, german, lang, pay, published
FROM active_tagged
WHERE no_german = 1
ORDER BY published DESC, refnr;
