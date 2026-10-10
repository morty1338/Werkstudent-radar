// UI language: English (default) or German, chosen with ?lang=de like the other
// filters. Every UI string lives in STRINGS below, both languages side by side.
// Entries are plain strings with {placeholders} or functions (for plurals and
// sentences that need reordering). Strings with HTML get already escaped values.
// No imports, so every module can use it.

export const lang = new URLSearchParams(location.search).get("lang") === "de" ? "de" : "en";
export const locale = lang === "de" ? "de-DE" : "en-GB";

const plural = (n, one, many) => (n === 1 ? one : many);

const STRINGS = {
  // --- Header, filters ---------------------------------------------------------------------------
  "brand.aria": { en: "Werkstudent Radar, back to top", de: "Werkstudent Radar, nach oben" },
  "nav.aria": { en: "Sections", de: "Abschnitte" },
  "nav.where": { en: "Jobs", de: "Jobs" },
  "nav.pay": { en: "Pay", de: "Gehalt" },
  "nav.skills": { en: "Skills", de: "Skills" },
  "nav.programmes": { en: "Degrees", de: "Studium" },
  "nav.trends": { en: "Trends", de: "Trends" },
  "nav.check": { en: "Your skills", de: "Deine Skills" },
  "nav.check_short": { en: "Match", de: "Match" },
  "lang.aria": { en: "Language", de: "Sprache" },
  "filter.field": { en: "Field", de: "Bereich" },
  "filter.city": { en: "City", de: "Stadt" },
  "filter.all_fields": { en: "All fields", de: "Alle Bereiche" },
  "filter.all_germany": { en: "All of Germany", de: "Ganz Deutschland" },
  "filter.no_german": { en: "No German needed", de: "Ohne Deutsch" },
  "filter.reset": { en: "Reset", de: "Zurücksetzen" },
  "filter.open": { en: "Filters", de: "Filter" },
  "filter.close": { en: "Close", de: "Schließen" },
  "filter.count": { en: "{n} jobs", de: "{n} Jobs" },
  "filter.show": { en: "Show {n} jobs", de: "{n} Jobs anzeigen" },
  "filter.chip_no_german": { en: "No German", de: "Ohne Deutsch" },
  "filter.remove": { en: "Remove filter: {x}", de: "Filter entfernen: {x}" },

  // --- Hero ------------------------------------------------------------------------------------------
  "hero.title": { en: "Werkstudent jobs in Germany, in&nbsp;numbers", de: "Werkstudentenjobs in Deutschland, in&nbsp;Zahlen" },
  "hero.lede": {
    en: ({ plus }) => `Every Werkstudent posting on the Bundesagentur für Arbeit job board${plus ? `, plus ${plus} from company career sites` : ""}.`,
    de: ({ plus }) => `Jede Werkstudentenstelle in der Jobbörse der Bundesagentur für Arbeit${plus ? `, dazu ${plus} von Karriereseiten der Unternehmen` : ""}.`,
  },
  "status.live": { en: "LIVE", de: "LIVE" },
  "status.stale": { en: "STALE", de: "VERALTET" },
  "status.last_scan": { en: "LAST SCAN", de: "LETZTER SCAN" },
  "status.stale_note": {
    en: "The daily update hasn't run for {n} days, so these numbers may be out of date.",
    de: "Das tägliche Update lief seit {n} Tagen nicht, die Zahlen können veraltet sein.",
  },
  "load.error": { en: "Couldn't load the data ({msg}). Please try again later.", de: "Die Daten konnten nicht geladen werden ({msg}). Bitte später erneut versuchen." },

  // --- Tiles -------------------------------------------------------------------------------------------
  "tile.jobs_where": { en: "Jobs · {where}", de: "Jobs · {where}" },
  "tile.jobs_online": { en: "Werkstudent jobs online", de: "Werkstudentenjobs online" },
  "tile.places": { en: ({ n, v }) => `in ${v} ${plural(n, "place", "places")}`, de: ({ n, v }) => `an ${v} ${plural(n, "Ort", "Orten")}` },
  "tile.median": { en: "Median pay", de: "Medianlohn" },
  "tile.per_hour": { en: "per hour · {ci}", de: "pro Stunde · {ci}" },
  "tile.top_skill": { en: "Most asked-for skill", de: "Meistgesuchter Skill" },
  "tile.skill_share": { en: "in {pct} of jobs", de: "in {pct} der Jobs" },
  "tile.most_jobs": { en: "Most jobs in", de: "Die meisten Jobs in" },
  "jobs.n": { en: ({ n, v }) => `${v} ${plural(n, "job", "jobs")}`, de: ({ v }) => `${v} Jobs` },

  // --- Pay statistics -------------------------------------------------------------------------------------
  "ci": { en: "95% CI €{lo}–{hi}", de: "95%-KI {lo}–{hi} €" },
  "why.few": { en: "too few rates stated", de: "zu wenige Lohnangaben" },
  "why.unsure": { en: "too few rates to be sure", de: "zu wenige Angaben für eine sichere Aussage" },

  // --- 01 Where ---------------------------------------------------------------------------------------------
  "where.title": { en: "Where are the jobs?", de: "Wo sind die Jobs?" },
  "where.by_place": { en: "By place", de: "Nach Ort" },
  "where.by_place_hint": { en: "click a bubble to filter", de: "Blase anklicken zum Filtern" },
  "where.by_field": { en: "By field", de: "Nach Bereich" },
  "where.by_field_hint": { en: "click to filter", de: "zum Filtern anklicken" },
  "where.map_aria": { en: "Map of Werkstudent postings by place", de: "Karte der Werkstudentenstellen nach Ort" },
  "where.field_tip": { en: "{n} jobs · {pct}", de: "{n} Jobs · {pct}" },
  "where.none": { en: "No jobs match these filters.", de: "Keine Jobs passen zu diesen Filtern." },
  "where.city": {
    en: ({ n, city, field }) => `<strong>${n}</strong> jobs in ${city}${field ? ` in ${field}` : ""}.`,
    de: ({ n, city, field }) => `<strong>${n}</strong> Jobs in ${city}${field ? ` im Bereich ${field}` : ""}.`,
  },
  "where.city_most": { en: " Most are in <strong>{field}</strong>.", de: " Die meisten im Bereich <strong>{field}</strong>." },
  "where.top": {
    en: ({ city, n, next }) => `<strong>${city}</strong> has the most jobs (${n})${next ? `, followed by ${next}` : ""}.`,
    de: ({ city, n, next }) => `<strong>${city}</strong> hat die meisten Jobs (${n})${next ? `, gefolgt von ${next}` : ""}.`,
  },
  "where.biggest": { en: " The biggest field is <strong>{field}</strong>.", de: " Der größte Bereich ist <strong>{field}</strong>." },
  "and": { en: " and ", de: " und " },
  "or": { en: " or ", de: " oder " },

  // --- 02 Pay --------------------------------------------------------------------------------------------------
  "pay.title": { en: "What does it pay?", de: "Was wird bezahlt?" },
  "pay.hourly": { en: "Hourly pay", de: "Stundenlohn" },
  "pay.range": { en: "Typical range", de: "Typische Spanne" },
  "pay.by_field": { en: "by field", de: "nach Bereich" },
  "pay.by_city": { en: "by city", de: "nach Stadt" },
  "pay.legend": {
    en: '<span class="lg-range"></span> middle half of rates <span class="lg-dot"></span> median',
    de: '<span class="lg-range"></span> mittlere Hälfte der Löhne <span class="lg-dot"></span> Median',
  },
  "pay.range_tip": {
    en: ({ label, median, ci, p25, p75, n, emp }) => `<strong>${label}</strong><br>Median ${median}/h · ${ci}<br>Half earn ${p25}–${p75}<br>${n} roles from ${emp} employers`,
    de: ({ label, median, ci, p25, p75, n, emp }) => `<strong>${label}</strong><br>Median ${median}/Std. · ${ci}<br>Die Hälfte verdient ${p25}–${p75}<br>${n} Rollen von ${emp} Arbeitgebern`,
  },
  "pay.one_employer": { en: "<br>{pct} of these rates come from one employer", de: "<br>{pct} dieser Löhne stammen von einem Arbeitgeber" },
  "pay.bin_top": { en: "€{lo} or more", de: "{lo} € oder mehr" },
  "pay.bin": { en: "€{lo}–{lo}.99", de: "{lo}–{lo},99 €" },
  "pay.roles": { en: ({ n, v }) => `${v} ${plural(n, "role", "roles")}`, de: ({ n, v }) => `${v} ${plural(n, "Rolle", "Rollen")}` },
  "pay.median_marker": { en: "median {v}", de: "Median {v}" },
  "pay.axis": { en: "€ per hour · {n} roles with a stated rate", de: "€ pro Stunde · {n} Rollen mit Lohnangabe" },
  "pay.q1": { en: "a quarter earn less", de: "ein Viertel verdient weniger" },
  "pay.median": { en: "median", de: "Median" },
  "pay.q3": { en: "a quarter earn more", de: "ein Viertel verdient mehr" },
  "pay.no_rates": { en: "No stated rates for this selection.", de: "Keine Lohnangaben für diese Auswahl." },
  "pay.too_few": {
    en: "Too few jobs state an hourly rate for this selection ({n}). Try widening the filters.",
    de: "Zu wenige Jobs nennen für diese Auswahl einen Stundenlohn ({n}). Versuche, die Filter zu erweitern.",
  },
  "pay.insight": {
    en: "Half of the jobs pay between <strong>{p25}</strong> and <strong>{p75}</strong> an hour.",
    de: "Die Hälfte der Jobs zahlt zwischen <strong>{p25}</strong> und <strong>{p75}</strong> pro Stunde.",
  },
  "pay.best": { en: " <strong>{label}</strong> pays the most ({v}).", de: " Am besten zahlt <strong>{label}</strong> ({v})." },
  "pay.dots_empty": { en: "Not enough pay data for this selection.", de: "Nicht genug Lohndaten für diese Auswahl." },

  // --- 03 Skills -------------------------------------------------------------------------------------------------
  "skills.title": { en: "Which skills are asked for?", de: "Welche Skills werden gesucht?" },
  "skills.all": { en: "All", de: "Alle" },
  "skills.bar_tip": { en: "{n} of {total} jobs", de: "{n} von {total} Jobs" },
  "skills.empty": { en: "No skills found for this selection.", de: "Keine Skills für diese Auswahl gefunden." },
  "skills.insight": { en: "<strong>{skill}</strong> is asked for in {pct} of jobs.", de: "<strong>{skill}</strong> wird in {pct} der Jobs gesucht." },
  "skills.prog": {
    en: " The most wanted programming language is <strong>{skill}</strong> ({pct}).",
    de: " Die gefragteste Programmiersprache ist <strong>{skill}</strong> ({pct}).",
  },
  "skills.related": { en: "Often asked together", de: "Oft zusammen gesucht" },
  "skills.related_tip": {
    en: "in {pct} of jobs asking for {skill}<br>{lift}× as often as by chance",
    de: "in {pct} der Jobs mit {skill}<br>{lift}× so oft wie zufällig erwartet",
  },
  "skills.pick": { en: "Pick a skill to see details.", de: "Wähle einen Skill für Details." },
  "skills.share": { en: "in {pct} of jobs · {n} postings", de: "in {pct} der Jobs · {n} Anzeigen" },
  "skills.median_pay": { en: "median pay", de: "Medianlohn" },
  "skills.vs_all": { en: " ({d} vs all)", de: " ({d} ggü. allen)" },
  "skills.in_field": { en: "in {field}", de: "in {field}" },
  "skills.where": { en: "Where it's asked for", de: "Wo er gesucht wird" },
  "skills.show_jobs": { en: "Show {n} jobs", de: "{n} Jobs anzeigen" },
  "skills.have": { en: "✓ In your skills", de: "✓ In deinen Skills" },
  "skills.add": { en: "+ I have this", de: "+ Kann ich" },

  // --- 04 Programmes -----------------------------------------------------------------------------------------------
  "programmes.title": { en: "What does your degree lead to?", de: "Wohin führt dein Studium?" },
  "programmes.jobs": { en: "Jobs mentioning it", de: "Jobs, die es nennen" },
  "programmes.share": { en: "Share of all jobs", de: "Anteil aller Jobs" },
  "programmes.median": { en: "Median pay", de: "Medianlohn" },
  "programmes.top_field": { en: "Top field", de: "Top-Bereich" },
  "programmes.fields": { en: "Fields", de: "Bereiche" },
  "programmes.skills": { en: "Skills they ask for", de: "Gesuchte Skills" },
  "programmes.skills_hint": { en: "click to add to yours", de: "anklicken, um ihn hinzuzufügen" },
  "programmes.newest": { en: "Newest postings", de: "Neueste Anzeigen" },

  // --- 05 Trends ----------------------------------------------------------------------------------------------------
  "trends.title": { en: "How is it changing?", de: "Wie verändert es sich?" },
  "trends.early": {
    en: "A snapshot is taken every morning since {date}. Trends appear after a few weeks.",
    de: "Seit {date} wird jeden Morgen ein Schnappschuss gemacht. Trends zeigen sich nach ein paar Wochen.",
  },
  "trends.days": { en: "{n} daily snapshots since {date}.", de: "{n} tägliche Schnappschüsse seit {date}." },
  "trends.jobs": { en: "Postings online", de: "Stellen online" },
  "trends.pay": { en: "Median hourly pay", de: "Medianer Stundenlohn" },
  "trends.pay_hint": { en: "shaded: 95% confidence interval", de: "schattiert: 95%-Konfidenzintervall" },
  "trends.postings": { en: "Postings", de: "Stellen" },
  "trends.median": { en: "Median pay", de: "Medianlohn" },
  "life.title": { en: "How long postings stay online", de: "Wie lange Stellen online bleiben" },
  "life.hint": { en: "share still online, by days since publication", de: "Anteil noch online, nach Tagen seit Veröffentlichung" },
  "life.median": {
    en: "Half of the postings are gone <strong>{n} days</strong> after publication.",
    de: "Die Hälfte der Anzeigen ist <strong>{n} Tage</strong> nach der Veröffentlichung verschwunden.",
  },
  "life.no_median": {
    en: "More than half are still online <strong>{n} days</strong> after publication; the median will show once more postings have gone offline.",
    de: "Mehr als die Hälfte ist <strong>{n} Tage</strong> nach der Veröffentlichung noch online; der Median erscheint, sobald mehr Anzeigen offline gegangen sind.",
  },
  "life.based": { en: " Based on {n} Bundesagentur postings, {gone} of them gone so far.", de: " Grundlage: {n} Anzeigen der Bundesagentur, davon bisher {gone} offline." },
  "life.shortest": { en: " Shortest: {list}.", de: " Am kürzesten: {list}." },
  "life.days": { en: "{n} days", de: "{n} Tage" },
  "life.empty": { en: "Not enough postings have gone offline yet.", de: "Noch sind nicht genug Anzeigen offline gegangen." },
  "life.tip": {
    en: "<strong>Day {d} after publication</strong><br>{pct} still online (95% CI {lo}–{hi})<br>{n} postings observed at the last step",
    de: "<strong>Tag {d} nach Veröffentlichung</strong><br>{pct} noch online (95%-KI {lo}–{hi})<br>{n} Anzeigen beobachtet beim letzten Schritt",
  },
  "life.aria": { en: "Still online after {d} days: {pct}", de: "Noch online nach {d} Tagen: {pct}" },
  "life.day_suffix": { en: "d", de: " T" },
  "chart.no_data": { en: "No data yet.", de: "Noch keine Daten." },
  "chart.latest": { en: "{label}: latest {v}", de: "{label}: zuletzt {v}" },
  "chart.ci": { en: " (95% CI {lo}–{hi})", de: " (95%-KI {lo}–{hi})" },

  // --- 06 Check your skills -------------------------------------------------------------------------------------------
  "check.title": { en: "Check your skills", de: "Prüfe deine Skills" },
  "check.insight": {
    en: "Tick what you can do, or let your CV fill it in, to see the share of these jobs you qualify for.",
    de: "Wähle aus, was du kannst, oder lass deinen Lebenslauf das übernehmen, und sieh, für welchen Anteil der Jobs du infrage kommst.",
  },
  "check.your_skills": { en: "Your skills", de: "Deine Skills" },
  "check.clear": { en: "Clear", de: "Leeren" },
  "check.search": { en: "Find a skill", de: "Skill suchen" },
  "check.search_ph": { en: "Find a skill: SQL, SAP, Figma…", de: "Skill suchen: SQL, SAP, Figma …" },
  "check.chip_title": { en: "Asked for in {n} postings", de: "In {n} Anzeigen gesucht" },
  "check.no_skill": { en: "No skill matches “{q}”.", de: "Kein Skill passt zu „{q}“." },
  "check.fewer": { en: "Show fewer skills", de: "Weniger Skills zeigen" },
  "check.all_skills": { en: "Show all {n} skills", de: "Alle {n} Skills zeigen" },
  "check.hide_jobs": { en: "Hide jobs", de: "Jobs ausblenden" },
  "check.empty": { en: "Pick a few skills on the left and this shows how many jobs fit.", de: "Wähle links ein paar Skills, dann siehst du hier, wie viele Jobs passen." },
  "check.browse": { en: "Browse all {n} jobs", de: "Alle {n} Jobs ansehen" },
  "check.fit": { en: "of jobs that list skills fit you: <strong>{n}</strong>{near}.", de: "der Jobs mit Skill-Angaben passen zu dir: <strong>{n}</strong>{near}." },
  "check.near": { en: ", and {n} more need one extra skill", de: ", für {n} weitere fehlt ein Skill" },
  "check.show_matching": { en: "Show {n} matching jobs", de: "{n} passende Jobs anzeigen" },
  "check.gap": {
    en: "Learn {names} to qualify for <strong>{n}</strong> more jobs ({from} → {to}).",
    de: "Lerne {names}, dann passen <strong>{n}</strong> weitere Jobs zu dir ({from} → {to}).",
  },
  "check.learn_next": { en: "Learn next", de: "Als Nächstes lernen" },
  "check.gap_first": { en: "Opens {n} more jobs", de: "Öffnet {n} weitere Jobs" },
  "check.gap_then": { en: "After the skills before it, opens {n} more jobs", de: "Nach den Skills davor: {n} weitere Jobs" },
  "check.tab_match": { en: "You qualify ({n})", de: "Passt ({n})" },
  "check.tab_near": { en: "One skill away ({n})", de: "Ein Skill fehlt ({n})" },
  "check.tab_all": { en: "All jobs ({n})", de: "Alle Jobs ({n})" },
  "check.asking_for": { en: "Jobs asking for {skill}", de: "Jobs mit {skill}" },
  "check.remove": { en: "Remove", de: "Entfernen" },
  "check.loading": { en: "Loading jobs…", de: "Jobs werden geladen …" },
  "check.load_error": { en: "Couldn't load the postings ({msg}).", de: "Die Anzeigen konnten nicht geladen werden ({msg})." },
  "check.updating": { en: "the data is being updated, please reload", de: "die Daten werden gerade aktualisiert, bitte neu laden" },
  "check.no_matches": { en: "No matches yet. Add skills, or check “One skill away”.", de: "Noch keine Treffer. Füge Skills hinzu oder schau unter „Ein Skill fehlt“." },
  "check.no_jobs": { en: "No jobs for this selection.", de: "Keine Jobs für diese Auswahl." },
  "check.more": { en: "Show more ({n} left)", de: "Mehr anzeigen (noch {n})" },
  "check.show_more": { en: "Show more", de: "Mehr anzeigen" },
  "check.no_german": { en: "No German needed", de: "Ohne Deutsch" },
  "check.german_plus": { en: "German a plus", de: "Deutsch ein Plus" },
  "check.per_hour": { en: "/h", de: "/Std." },
  "check.headline": { en: "{n} jobs fit your {k} skills →", de: "{n} Jobs passen zu deinen {k} Skills →" },
  "sort.label": { en: "Sort", de: "Sortieren" },
  "sort.best": { en: "Best fit first", de: "Beste Passung zuerst" },
  "sort.newest": { en: "Newest first", de: "Neueste zuerst" },
  "sort.pay": { en: "Highest pay first", de: "Höchster Lohn zuerst" },

  // CV
  "cv.upload": { en: "Upload CV", de: "Lebenslauf hochladen" },
  "cv.title": { en: "Your CV is read in your browser and never uploaded", de: "Dein Lebenslauf wird nur in deinem Browser gelesen und nie hochgeladen" },
  "cv.reading": { en: "Reading {file}…", de: "Lese {file} …" },
  "cv.no_text": {
    en: "No text found in {file}. A scanned PDF can't be read; tick your skills by hand instead.",
    de: "Kein Text in {file} gefunden. Ein gescanntes PDF lässt sich nicht lesen; wähle deine Skills stattdessen von Hand.",
  },
  "cv.no_skills": { en: "No skills from our list found in {file}.", de: "Keine Skills aus unserer Liste in {file} gefunden." },
  "cv.found": { en: "✓ {n} skills found in your CV and ticked below", de: "✓ {n} Skills in deinem Lebenslauf gefunden und unten ausgewählt" },
  "cv.degree": { en: " · degree: ", de: " · Studium: " },
  "cv.error": { en: "Couldn't read {file}: {msg}.", de: "{file} konnte nicht gelesen werden: {msg}." },
  "cv.too_big": { en: "the file is larger than 10 MB", de: "die Datei ist größer als 10 MB" },
  "cv.format": { en: "please use a PDF, DOCX or TXT file", de: "bitte eine PDF-, DOCX- oder TXT-Datei verwenden" },

  // Subscribe
  "subscribe.summary": { en: "Subscribe to new jobs", de: "Neue Jobs abonnieren" },
  "subscribe.text": {
    en: "RSS feeds of postings that are new on the market, updated every morning. Paste a link into a feed reader (Feedly, Inoreader, NetNewsWire…); each item links to the original posting.",
    de: "RSS-Feeds mit Stellen, die neu am Markt sind, jeden Morgen aktualisiert. Füge einen Link in einen Feedreader ein (Feedly, Inoreader, NetNewsWire …); jeder Eintrag verlinkt die Originalanzeige.",
  },
  "subscribe.all": { en: "All new Werkstudent jobs", de: "Alle neuen Werkstudentenjobs" },
  "subscribe.field": { en: "New jobs in {field}", de: "Neue Jobs: {field}" },
  "subscribe.copy": { en: "Copy link", de: "Link kopieren" },
  "subscribe.copied": { en: "Copied ✓", de: "Kopiert ✓" },
  "subscribe.hint": { en: "Pick a field in the filters to get a feed for just that field.", de: "Wähle in den Filtern einen Bereich für einen Feed nur dieses Bereichs." },

  // --- 07 SQL playground ---------------------------------------------------------------------------------------------
  "query.title": { en: "Query the data yourself", de: "Frag die Daten selbst ab" },
  "query.insight": {
    en: "Every posting since the first scan as one table: field, city, pay, German, skills, first and last seen. SQL runs in your browser with DuckDB. No job texts.",
    de: "Jede Stelle seit dem ersten Scan als eine Tabelle: Bereich, Stadt, Lohn, Deutsch, Skills, zuerst und zuletzt gesehen. SQL läuft in deinem Browser mit DuckDB. Keine Stellentexte.",
  },
  "query.open": { en: "Open the SQL playground", de: "SQL-Playground öffnen" },
  "query.open_hint": { en: "loads DuckDB-WASM (a few MB) from jsDelivr when opened", de: "lädt beim Öffnen DuckDB-WASM (einige MB) von jsDelivr" },
  "query.label": { en: "SQL query", de: "SQL-Abfrage" },
  "query.run": { en: "Run", de: "Ausführen" },
  "query.loading": { en: "Loading DuckDB (a few MB, once)…", de: "DuckDB wird geladen (einmalig, einige MB) …" },
  "query.running": { en: "Running…", de: "Läuft …" },
  "query.rows": {
    en: ({ n, v, ms }) => `${v} ${plural(n, "row", "rows")} in ${ms} ms`,
    de: ({ n, v, ms }) => `${v} ${plural(n, "Zeile", "Zeilen")} in ${ms} ms`,
  },
  "query.first": { en: " · first {m} shown", de: " · erste {m} angezeigt" },
  "query.ex1": { en: "Median pay by field", de: "Medianlohn nach Bereich" },
  "query.ex2": { en: "Skills in jobs without German", de: "Skills in Jobs ohne Deutsch" },
  "query.ex3": { en: "Best-paid skills", de: "Bestbezahlte Skills" },
  "query.ex4": { en: "IT jobs from €18/h by city", de: "IT-Jobs ab 18 €/Std. nach Stadt" },
  "query.help": {
    en: 'Tables: <code>postings</code> (refnr, source, title, company, field, field_label, city, lat, lon, pay, pay_min, pay_max, german, remote, published, first_seen, last_seen, online, skills[], url) and <code>skills</code> (id, label, group). Pay is €/h; <code>german</code> is required, implicit, plus or none. Download: <a href="data/postings.parquet" download>postings.parquet</a>, <a href="data/skills.parquet" download>skills.parquet</a>.',
    de: 'Tabellen: <code>postings</code> (refnr, source, title, company, field, field_label, city, lat, lon, pay, pay_min, pay_max, german, remote, published, first_seen, last_seen, online, skills[], url) und <code>skills</code> (id, label, group). Lohn in €/Std.; <code>german</code> ist required, implicit, plus oder none. Download: <a href="data/postings.parquet" download>postings.parquet</a>, <a href="data/skills.parquet" download>skills.parquet</a>.',
  },

  // --- About, footer -------------------------------------------------------------------------------------------------
  "about.summary": { en: "About the data", de: "Über die Daten" },
  "about.body": {
    en: `<p><strong>Sources.</strong> Every morning a script collects all postings with “Werkstudent”, “Working Student” or “Werkstudierende” in the title from the public job search of the <a href="https://www.arbeitsagentur.de/jobsuche/">Bundesagentur für Arbeit</a>, plus Werkstudent postings from companies' own career sites through the free <a href="https://www.arbeitnow.com/">Arbeitnow</a> job API. A posting found in both counts once. LinkedIn, StepStone and Indeed don't allow automated collection and aren't used; many of their postings come from the same company career sites.</p>
<p><strong>Pay</strong> comes from the posting's salary fields or phrases like “17,50 € pro Stunde”. Each role counts once; a median needs at least 10 roles and is shown with its 95% confidence interval.</p>
<p><strong>Skills and German</strong> are found by rules with German and English synonyms, checked against 100 labelled postings. <a href="https://github.com/morty1338/werkstudent-radar#accuracy">How accurate they are</a>.</p>
<p><strong>Your CV</strong> is read and analysed in your browser with the same rules. It is never uploaded or stored.</p>
<p>Job texts belong to the employers and aren't published here; links lead to the originals. Code and data: <a href="https://github.com/morty1338/werkstudent-radar">github.com/morty1338/werkstudent-radar</a>.</p>`,
    de: `<p><strong>Quellen.</strong> Jeden Morgen sammelt ein Skript alle Anzeigen mit „Werkstudent“, „Working Student“ oder „Werkstudierende“ im Titel aus der öffentlichen Jobsuche der <a href="https://www.arbeitsagentur.de/jobsuche/">Bundesagentur für Arbeit</a>, dazu Werkstudentenstellen von Karriereseiten der Unternehmen über die kostenlose Job-API von <a href="https://www.arbeitnow.com/">Arbeitnow</a>. Eine Anzeige, die in beiden vorkommt, zählt einmal. LinkedIn, StepStone und Indeed erlauben kein automatisches Sammeln und werden nicht genutzt; viele ihrer Anzeigen stammen von denselben Karriereseiten.</p>
<p><strong>Löhne</strong> stammen aus den Gehaltsfeldern der Anzeige oder aus Formulierungen wie „17,50 € pro Stunde“. Jede Rolle zählt einmal; ein Median braucht mindestens 10 Rollen und wird mit seinem 95%-Konfidenzintervall gezeigt.</p>
<p><strong>Skills und Deutsch</strong> werden mit Regeln mit deutschen und englischen Synonymen erkannt und an 100 annotierten Anzeigen geprüft. <a href="https://github.com/morty1338/werkstudent-radar#accuracy">Wie genau sie sind</a>.</p>
<p><strong>Dein Lebenslauf</strong> wird in deinem Browser mit denselben Regeln gelesen und ausgewertet. Er wird nie hochgeladen oder gespeichert.</p>
<p>Stellentexte gehören den Arbeitgebern und werden hier nicht veröffentlicht; Links führen zu den Originalen. Code und Daten: <a href="https://github.com/morty1338/werkstudent-radar">github.com/morty1338/werkstudent-radar</a>.</p>`,
  },
  "footer": {
    en: 'Werkstudent Radar · data: Bundesagentur für Arbeit and company career sites via <a href="https://www.arbeitnow.com/">Arbeitnow</a> · <a href="https://github.com/morty1338/werkstudent-radar">source code</a>',
    de: 'Werkstudent Radar · Daten: Bundesagentur für Arbeit und Karriereseiten der Unternehmen über <a href="https://www.arbeitnow.com/">Arbeitnow</a> · <a href="https://github.com/morty1338/werkstudent-radar">Quellcode</a>',
  },

  // --- Data labels (fields, skill groups, a few skills) ---------------------------------------------------------------
  "field.admin": { en: "Office & Admin", de: "Büro & Verwaltung" },
  "field.consulting": { en: "Consulting & Strategy", de: "Beratung & Strategie" },
  "field.data": { en: "Data & Analytics", de: "Daten & Analytics" },
  "field.design": { en: "Design & UX", de: "Design & UX" },
  "field.education": { en: "Education & Social", de: "Bildung & Soziales" },
  "field.engineering": { en: "Engineering & Production", de: "Ingenieurwesen & Produktion" },
  "field.finance": { en: "Finance & Controlling", de: "Finanzen & Controlling" },
  "field.health": { en: "Health & Care", de: "Gesundheit & Pflege" },
  "field.hr": { en: "HR & Recruiting", de: "HR & Recruiting" },
  "field.it": { en: "IT & Software", de: "IT & Software" },
  "field.legal": { en: "Legal", de: "Recht" },
  "field.marketing": { en: "Marketing & Communication", de: "Marketing & Kommunikation" },
  "field.ops": { en: "Operations & Logistics", de: "Operations & Logistik" },
  "field.other": { en: "Other", de: "Sonstiges" },
  "field.product": { en: "Product & Project Mgmt", de: "Produkt- & Projektmanagement" },
  "field.research": { en: "Research & Science", de: "Forschung & Wissenschaft" },
  "field.retail": { en: "Retail & Hospitality", de: "Handel & Gastronomie" },
  "field.sales": { en: "Sales & Business Development", de: "Vertrieb & Business Development" },
  "group.Business & Finance": { de: "Business & Finanzen" },
  "group.Data & AI": { de: "Daten & KI" },
  "group.Design & Media": { de: "Design & Medien" },
  "group.Engineering": { de: "Ingenieurwesen" },
  "group.IT & Security": { de: "IT & Sicherheit" },
  "group.Marketing & Sales": { de: "Marketing & Vertrieb" },
  "group.Office & Tools": { de: "Office & Tools" },
  "group.Programming": { de: "Programmierung" },
  "group.Science & Lab": { de: "Wissenschaft & Labor" },
  "group.Web & Mobile": { de: "Web & Mobile" },
  "skill.driving_licence": { de: "Führerschein (B)" },
  "skill.sap": { de: "SAP (allgemein)" },
  "skill.social_media": { de: "Social Media" },
  "skill.other_erp": { de: "ERP (sonstige)" },
  "skill.cad": { de: "CAD (allgemein)" },
  "skill.crm": { de: "CRM-Systeme" },
  "skill.content": { de: "Content-Erstellung / Texten" },
  "skill.project_mgmt": { de: "Projektmanagement" },
  "skill.sales_skills": { de: "Vertrieb / Business Development" },
  "skill.video": { de: "Videoschnitt" },
  "skill.data_analysis": { de: "Datenanalyse" },
  "skill.accounting": { de: "Buchhaltung / Rechnungswesen" },
  "skill.process_mgmt": { de: "Prozessmanagement / BPMN" },
  "skill.customer_service": { de: "Kundenservice" },
  "skill.supply_chain": { de: "Supply Chain / Logistik" },
  "skill.procurement": { de: "Einkauf" },
  "skill.it_security": { de: "IT-Sicherheit" },
  "skill.mechanical": { de: "Konstruktion" },
  "skill.consulting": { de: "Beratung" },
  "skill.quality": { de: "Qualitätsmanagement (ISO 9001)" },
  "skill.labour_law": { de: "Recht / Arbeitsrecht" },
  "skill.electrical": { de: "Elektrotechnik" },
  "skill.online_marketing": { de: "Online-Marketing" },
  "skill.testing": { de: "Softwaretests / QA" },
  "skill.pr": { de: "PR / Kommunikation" },
  "skill.tax": { de: "Steuern" },
  "skill.graphic_design": { de: "Grafikdesign" },
  "skill.event": { de: "Eventmanagement" },
  "skill.audit": { de: "Prüfung / Audit" },
  "skill.photography": { de: "Fotografie" },
  "skill.dataviz": { de: "Datenvisualisierung" },
  "skill.energy": { de: "Energiesysteme / PV" },
  "skill.it_support": { de: "IT-Support" },
  "skill.networking": { de: "Netzwerke" },
  "skill.statistics": { de: "Statistik" },
  "skill.lab": { de: "Laborarbeit" },
  "skill.robotics": { de: "Robotik / ROS" },
  "skill.embedded": { de: "Embedded Systems" },
  "skill.market_research": { de: "Marktforschung" },
  "skill.email_marketing": { de: "E-Mail-Marketing" },
  "skill.fin_model": { de: "Finanzmodelle / Bewertung" },
  "skill.pcb": { de: "Elektronik / Platinendesign" },
  "skill.virtualization": { de: "Virtualisierung" },
  "skill.production": { de: "Produktion / Fertigung" },
  "skill.ux": { de: "UX- / UI-Design" },
  "skill.vba": { de: "VBA / Makros" },

  "noscript": { en: "This page needs JavaScript to load the data.", de: "Diese Seite braucht JavaScript, um die Daten zu laden." },
};

// t("filter.count", { n: "4,822" }); a function entry gets the vars object.
export function t(key, vars = {}) {
  const entry = STRINGS[key];
  if (!entry) return key;
  const s = entry[lang] ?? entry.en;
  if (typeof s === "function") return s(vars);
  return s.replace(/\{(\w+)\}/g, (_, k) => (vars[k] ?? ""));
}

// Translated data labels; fall back to the label from the data.
const optional = (key, fallback) => (lang === "de" && STRINGS[key]?.de) || fallback;
export const fieldLabel = (id, fallback) => optional(`field.${id}`, fallback);
export const groupLabel = (group) => optional(`group.${group}`, group);
export const skillLabel = (id, fallback) => optional(`skill.${id}`, fallback);

// Static text in index.html: data-i18n (text), data-i18n-html (trusted markup from
// STRINGS), data-i18n-attr="attr:key;attr:key".
export function applyStatic(root = document) {
  document.documentElement.lang = lang;
  for (const el of root.querySelectorAll("[data-i18n]")) el.textContent = t(el.dataset.i18n);
  for (const el of root.querySelectorAll("[data-i18n-html]")) el.innerHTML = t(el.dataset.i18nHtml);
  for (const el of root.querySelectorAll("[data-i18n-attr]")) {
    for (const pair of el.dataset.i18nAttr.split(";")) {
      const [attr, key] = pair.split(":");
      el.setAttribute(attr, t(key));
    }
  }
  for (const b of root.querySelectorAll("[data-lang]")) b.setAttribute("aria-pressed", String(b.dataset.lang === lang));
}

// Switching language reloads the page with ?lang= set (the other filters stay in the URL).
export function initLangSwitch() {
  for (const b of document.querySelectorAll("[data-lang]")) {
    b.addEventListener("click", () => {
      if (b.dataset.lang === lang) return;
      const url = new URL(location.href);
      if (b.dataset.lang === "en") url.searchParams.delete("lang");
      else url.searchParams.set("lang", b.dataset.lang);
      location.href = url.href;
    });
  }
}

// Keys for tests: every key must have an English text.
export const KEYS = Object.keys(STRINGS);
export const missingEnglish = () => KEYS.filter((k) => !k.startsWith("group.") && !k.startsWith("skill.") && STRINGS[k].en == null);
export const missingGerman = () => KEYS.filter((k) => STRINGS[k].de == null);
