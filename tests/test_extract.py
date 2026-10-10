"""Rule tests for radar.extract, on short made-up snippets (no real job texts)."""

import pytest

from radar.extract import (
    classify,
    find_majors,
    find_skills,
    german_requirement,
    hourly_pay_from_text,
    hourly_pay_structured,
    hours_per_week,
    is_werkstudent,
    normalise_city,
    posting_language,
)


def german(text):
    return german_requirement(text, posting_language(text))


# --- German requirement -------------------------------------------------------

@pytest.mark.parametrize("text", [
    "Du sprichst fließend Deutsch und Englisch.",
    "Sehr gute Deutsch- und Englischkenntnisse in Wort und Schrift",
    "Sehr gute Englisch- und Deutschkenntnisse",
    "Deutschkenntnisse auf C1-Niveau",
    "Deutsch (mind. C1) ist ein Muss",
    "You are fluent in German and English.",
    "Excellent command of German is required.",
    "German C1 or higher",
])
def test_german_required(text):
    assert german(text) == "required"


@pytest.mark.parametrize("text", [
    "Deutschkenntnisse sind von Vorteil.",
    "German language skills are a plus.",
    "Nice to have: basic German",
    "Fluent English required, good German is beneficial.",
])
def test_german_plus(text):
    assert german(text) == "plus"


@pytest.mark.parametrize("text", [
    "German is not required, our working language is English.",
    "No German skills needed for this role.",
    "This is an English-only team.",
    "We are looking for a student who loves data. You will work with our analytics team in Berlin.",
])
def test_german_not_needed(text):
    assert german(text) == "none"


def test_german_implicit_for_german_posting_without_mention():
    text = "Wir suchen dich zur Unterstützung unseres Teams im Einkauf. Du bist eingeschrieben und hast Lust auf Neues."
    assert german(text) == "implicit"


def test_germany_is_not_german():
    text = "We are one of the fastest growing companies in Germany and strong in the German market."
    assert german(text) == "none"


def test_posting_language():
    assert posting_language("Wir suchen dich für unser Team und du bist motiviert.") == "de"
    assert posting_language("We are looking for you to join our team and you are motivated.") == "en"


# --- Pay ------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("Vergütung: 17,50 €/Stunde", (17.5, 17.5)),
    ("Stundenlohn von 15 - 18 Euro brutto", (15.0, 18.0)),
    ("Wir zahlen 16 € pro Stunde.", (16.0, 16.0)),
    ("an hourly rate of €18", (18.0, 18.0)),
    ("15,00 € bis 17,00 € brutto pro Stunde", (15.0, 17.0)),
])
def test_hourly_pay_from_text(text, expected):
    assert hourly_pay_from_text(text) == expected


@pytest.mark.parametrize("text", [
    "Wir zahlen 1.200 € pro Monat bei 20 Stunden pro Woche.",
    "30 Tage Urlaub und ein Zuschuss von 50 € zum Deutschlandticket.",
    "Umsatz von 15 Mio. €, 20 Stunden pro Woche",
])
def test_no_hourly_pay(text):
    assert hourly_pay_from_text(text) is None


def test_hourly_pay_structured():
    assert hourly_pay_structured({"verguetungsangabe": "STUNDENLOHN", "festgehalt": 16.0}) == (16.0, 16.0)
    assert hourly_pay_structured({"verguetungsangabe": "STUNDENLOHN", "gehaltsspanneVon": 15.67, "gehaltsspanneBis": 18.09}) == (15.67, 18.09)
    assert hourly_pay_structured({"verguetungsangabe": "JAHRESGEHALT", "festgehalt": 29023.2}) is None
    assert hourly_pay_structured({"verguetungsangabe": "STUNDENLOHN", "festgehalt": 1500}) is None


@pytest.mark.parametrize("text,expected", [
    ("für 20 Stunden pro Woche", 20),
    ("15-20 Std./Woche", 20),
    ("up to 20 hours per week", 20),
    ("Ab 16 Wochenstunden", 16),
    ("Wir haben 30 Mitarbeitende", None),
])
def test_hours_per_week(text, expected):
    assert hours_per_week(text) == expected


# --- Skills -------------------------------------------------------------------

def test_skills_synonyms():
    skills = find_skills("Erste Erfahrung mit SQL, Python und MS Excel; Kenntnisse in Power BI sind von Vorteil.")
    assert {"sql", "python", "excel", "powerbi"} <= set(skills)


def test_skills_avoid_common_words():
    skills = find_skills("You will excel at teamwork and react quickly. Java coffee? Our R&D team in Germany.")
    assert "excel" not in skills
    assert "react" not in skills
    assert "r" not in skills
    assert "javascript" not in skills


def test_java_vs_javascript():
    assert "java" not in find_skills("Kenntnisse in JavaScript")
    assert "javascript" in find_skills("Kenntnisse in JavaScript")
    assert "java" in find_skills("Kenntnisse in Java und Spring Boot")


def test_r_language_in_lists():
    assert "r" in find_skills("Kenntnisse in Python oder R")
    assert "r" in find_skills("Statistiksoftware (R, SPSS)")


# --- Majors, categories, misc ---------------------------------------------------

def test_majors_wirtschaftsinformatik_is_not_informatik():
    assert find_majors("Studium der Wirtschaftsinformatik") == ["wiinf"]
    assert set(find_majors("Studium der (Wirtschafts-)Informatik oder BWL")) == {"wiinf", "inf", "bwl"}
    assert find_majors("Studium des Wirtschaftsingenieurwesens") == ["wiing"]


@pytest.mark.parametrize("title,beruf,expected", [
    ("Werkstudent (m/w/d) Data Analytics", "", "data"),
    ("Werkstudent IT-Support (m/w/d)", "", "it"),
    ("Working Student Software Engineering (f/m/d)", "", "it"),
    ("Werkstudent Marketing & Social Media", "", "marketing"),
    ("Werkstudent (m/w/d)", "Helfer/in - Verkauf", "retail"),
    ("Werkstudent Controlling (m/w/d)", "", "finance"),
    ("Werkstudent:in HR / Recruiting", "", "hr"),
    ("Werkstudent Kundenberatung & Fahrzeugankauf (m/w/d)", "Fachverkäufer/in - Kraftfahrzeuge", "sales"),
    ("Werkstudent Consulting & Strategy", "", "consulting"),
])
def test_classify(title, beruf, expected):
    assert classify(title, beruf) == expected


def test_is_werkstudent():
    assert is_werkstudent("Werkstudent:in Marketing (m/w/d)")
    assert is_werkstudent("Working Student Finance")
    assert not is_werkstudent("Büroaushilfe (m/w/d)")
    assert is_werkstudent("Werksstudent Consulting Finance (m/w/d)")
    assert is_werkstudent("Werkstundent:in Marketing")
    assert not is_werkstudent("Werkstatt-Mitarbeiter (m/w/d)")


def test_normalise_city():
    assert normalise_city("Ingolstadt, Donau") == "Ingolstadt"
    assert normalise_city("Frankfurt") == "Frankfurt am Main"
    assert normalise_city("Berlin") == "Berlin"


# --- Regressions found while checking real postings ------------------------------

@pytest.mark.parametrize("text", [
    "Sehr gute Deutschkenntnisse, gute Englischkenntnisse von Vorteil.",
    "- Sehr gute Deutsch- und gute Englischkenntnisse.\n- Erfahrung mit KI-Tools sind von Vorteil.",
    "Deutsch und Englisch sehr gut in Wort und Schrift",
    "Sprachkenntnisse: Deutsch: fließend, Englisch: fließend",
    "Mindestens Deutsch A2 Sprachkenntnisse erforderlich.",
    "Idealerweise erste Erfahrung mit Python. Sehr gute Deutschkenntnisse sind Voraussetzung.",
])
def test_german_required_regressions(text):
    assert german(text) == "required"


def test_voucher_is_not_hourly_pay():
    text = "Neben Ihrem attraktiven Stundenlohn erhalten Sie monatlich einen 25 €-Gutschein für Getränke."
    assert hourly_pay_from_text(text) is None


@pytest.mark.parametrize("text,expected", [
    ("15,19 € pro Stunde / Direkt Dialog", (15.19, 15.19)),
    ("18,00 € brutto/Std. bei bis zu 20 Std./Woche", (18.0, 18.0)),
    ("Vergütung in Höhe von 16 Euro / Stunde", (16.0, 16.0)),
    ("Du erhältst einen Stundensatz von 14 EUR / Stunde", (14.0, 14.0)),
])
def test_hourly_pay_regressions(text, expected):
    assert hourly_pay_from_text(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("17,50 € pro Stunde", (17.5, 17.5)),
    ("17,50 EUR pro Stunde", (17.5, 17.5)),
    ("17.50 €/h", (17.5, 17.5)),
    ("€17.50/hour", (17.5, 17.5)),
    ("Stundenlohn: 17,50 €", (17.5, 17.5)),
    ("17,– € pro Stunde", (17.0, 17.0)),               # whole euros written with a dash
    ("15,- bis 17,- € pro Stunde", (15.0, 17.0)),
    ("17.50 euros per hour", (17.5, 17.5)),
    ("13,90 € pro Stunde (Mindestlohn)", (13.9, 13.9)),
    ("17,50 € pro Stunde zzgl. 50 € Zuschuss", (17.5, 17.5)),
])
def test_hourly_pay_formats(text, expected):
    assert hourly_pay_from_text(text) == expected


@pytest.mark.parametrize("text", [
    "538 € im Monat",
    "2.000 € brutto monatlich",
    "45.000 € Jahresgehalt",
    "8,50 € pro Stunde",       # below any legal minimum wage: a typo or an old posting
    "75 € pro Stunde",         # freelance rate, not a Werkstudent wage
])
def test_monthly_yearly_and_implausible_amounts_are_not_hourly_pay(text):
    assert hourly_pay_from_text(text) is None


@pytest.mark.parametrize("text", [
    "Idealerweise erste Erfahrungen mit SAP✓ Sehr gute Deutschkenntnisse✓ Teamfähigkeit",
    "Sehr gute Deutschkenntnisse, Englischkenntnisse sind von Vorteil",
    "Kommunikationsfähigkeit auf Muttersprachler Niveau in Deutsch, Englisch von Vorteil",
    "Kenntnisse in IT-Security wünschenswert Sehr gute Deutsch- und Englischkenntnisse",
])
def test_softener_belongs_to_neighbour_item(text):
    assert german(text) == "required"


def test_idealerweise_german_is_plus():
    assert german("Idealerweise gute Deutschkenntnisse") == "plus"


@pytest.mark.parametrize("text", [
    "gute Deutschkenntnisse, weitere Sprachen von Vorteil",
    "Du kommunizierst sicher in Deutsch und Englisch – weitere Sprachkenntnisse sind ein Plus",
])
def test_other_languages_softener_is_not_about_german(text):
    assert german(text) == "required"


# --- Regressions from the hand-labelled evaluation sample (data/eval) -----------

@pytest.mark.parametrize("text", [
    "Fließende Deutsch- und Englischkenntnisse, Russisch und Ukrainisch von Vorteil",
    "Fluent in English and German, French is beneficial but not required.",
    "Verhandlungssichere Deutschkenntnisse und wünschenswert gute Englischkenntnisse",
    "Language skills: English & German",
    "You are fluent in business English and German (spoken and written).",
    "Du kommunizierst auf Deutsch und Englisch",
    "Du bringst sehr gute #Deutsch- und Englischkenntnisse mit",
    "Deutsch- ([A2-Niveau](https://example.org)) und Englischkenntnisse",
    "You communicate fluent in English with a basic understanding in German.",
])
def test_german_required_eval_regressions(text):
    assert german(text) == "required"


@pytest.mark.parametrize("text", [
    "German language skills are a strong advantage.",
    "English fluency is a must, proficiency in French, German, Spanish or any other language is a plus.",
    "Gute Deutsch- und Englischkenntnisse sind von Vorteil",
])
def test_german_plus_eval_regressions(text):
    assert german(text) == "plus"


def test_pay_range_with_zwischen_und():
    text = "Wir bieten für diese Position einen Stundenlohn zwischen 14,50 € und 16,00 €."
    assert hourly_pay_from_text(text) == (14.5, 16.0)


def test_python_typo():
    assert "python" in find_skills("Kenntnisse in Phyton wünschenswert")


@pytest.mark.parametrize("title,beruf,expected", [
    ("Werkstudent Datenschutz (m/w/d)", "Datenschutzbeauftragte/r", "legal"),
    ("Werkstudent Steuerliches Rechenzentrum (w/m/d)", "", "it"),
    ("Werkstudent Kommunikationsdesign (m/w/d)", "", "design"),
    ("Werkstudent*in Personalentwicklung & KI-Transformation", "", "hr"),
    ("Werkstudent*in Cyber Security, SIEM & AI Security", "", "it"),
    ("Werkstudent / Sales Assistant (m/w/d) - Outlet", "Verkäufer/in", "retail"),
    ("Werkstudent Kreditorenmanagement in der WEG-Verwaltung", "", "finance"),
    ("Werkstudent (m/w/d) Digitalization & Technology", "Kaufmann/-frau - Büromanagement", "it"),
    ("Werkstudent Marktspezifische Sortimente", "Betriebswirt/in (Hochschule)", "other"),
    ("Werkstudent/in (m/w/d) 36, GIC Büro Köln", "Geoinformatiker/in", "it"),
    ("Werkstudent Data Analytics", "", "data"),
])
def test_classify_eval_regressions(title, beruf, expected):
    assert classify(title, beruf) == expected


@pytest.mark.parametrize("title,expected", [
    ("Werkstudent Personalentwicklung", "hr"),
    ("Werkstudent im Bereich Personal (m/w/d)", "hr"),
    ("Werkstudent Personal Assistant to the CEO", "admin"),
])
def test_classify_personal(title, expected):
    assert classify(title, "") == expected


@pytest.mark.parametrize("title,beruf,expected", [
    ("Werkstudent Digital Marketing (PR & AI Search)", "", "marketing"),
    ("Werkstudent KI & Digitalisierung (m/w/d)", "", "it"),
    ("Werkstudent (m/w/d)", "Personaldienstleistungskaufmann/-frau", "hr"),
    ("Werkstudent Personalvermittlung (m/w/d)", "", "hr"),
])
def test_classify_ai_fallback_and_personal(title, beruf, expected):
    assert classify(title, beruf) == expected
