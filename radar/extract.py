"""Turn one job posting (listing + full text) into aggregate-friendly features.

The description text is only used here, in memory. Nothing from it is stored
except the derived features below (skills, language, pay, majors, hours).
"""

import re

from .skills import CONTEXT_REQUIRED, SKILLS

# Bump whenever skills.py or the rules below change. Active jobs tagged with an
# older version are re-fetched and re-tagged on the next run.
EXTRACTOR_VERSION = 3

_FLAGS = re.IGNORECASE

_SKILL_RX = [(sid, re.compile("|".join(f"(?:{p})" for p in pats), _FLAGS)) for sid, _, _, pats in SKILLS]


_SKILL_CUE = re.compile(
    r"kenntnis|erfahrung|know-?how|knowledge|experience|familiar|vertraut|verständnis|understanding"
    r"|affinität|grundlagen|skills?\b|fähigkeit|umgang mit|proficien|expertise|background|versiert"
    r"|fundiert|interesse an|interest in|begeisterung für|passion for|hands-on",
    _FLAGS,
)


def _has_cue(text, m):
    return bool(_SKILL_CUE.search(text, max(0, m.start() - 80), m.end() + 40))


def find_skills(text, require_context=True):
    """Skill ids mentioned in text. In job postings, broad domain terms need a
    requirement cue nearby; a CV lists the person's own skills, so the site
    analyses CVs with require_context=False."""
    found = []
    for sid, rx in _SKILL_RX:
        if require_context and sid in CONTEXT_REQUIRED:
            if any(_has_cue(text, m) for m in rx.finditer(text)):
                found.append(sid)
        elif rx.search(text):
            found.append(sid)
    return sorted(found)


# --- Posting language ----------------------------------------------------

_DE_WORDS = set("der die das und ist wir sie mit für eine einen nicht auf bei zu von dein deine du ihre unser unsere werden sind oder als auch".split())
_EN_WORDS = set("the and you we with for our are will to of your in is be this as an or have who".split())


def posting_language(text):
    words = re.findall(r"[a-zäöüß]+", text.lower())
    de = sum(w in _DE_WORDS for w in words)
    en = sum(w in _EN_WORDS for w in words)
    if de == 0 and en == 0:
        return "de"
    return "en" if en > de * 1.2 else "de"


# --- German requirement ----------------------------------------------------
# Returns one of:
#   required  – explicit "fließend Deutsch", "German C1", "sehr gute Deutschkenntnisse"…
#   plus      – German is "von Vorteil" / "a plus" / "nice to have"
#   none      – "English only", "no German required", or an English posting that
#               never asks for German
#   implicit  – German-language posting that doesn't mention it (in practice German needed)

_ADJ_DE = r"(?:flie(?:ß|ss)end\w*|verhandlungssicher\w*|sehr gut\w*|exzellent\w*|ausgezeichnet\w*|hervorragend\w*|gut\w*|sicher\w*|perfekt\w*|einwandfrei\w*|stilsicher\w*|muttersprachl\w*|fundiert\w*|solid\w*|profund\w*)"
_DEUTSCH = r"deutsch(?!land|en? (?:markt|kunden|unternehmen|standort))"

_REQ = [
    rf"{_ADJ_DE}\s+(?:[\w\-/]+\s+){{0,3}}{_DEUTSCH}",
    rf"{_DEUTSCH}\w*\s*(?:\(|\[|-|:|–|auf|mind\.?|mindestens|niveau|level|sprachniveau|\s)*\s*(?:a2|b1|b2|c1|c2)\b",
    rf"(?:kommunizierst|sprichst|sprechen|kommunizieren|verständigen?)\s+(?:\w+\s+){{0,3}}(?:auf|in)\s+deutsch\b",
    rf"{_DEUTSCH}\w*\s*[:\-–]?\s*(?:in wort und schrift|flie(?:ß|ss)end|verhandlungssicher|auf muttersprach|als muttersprache|sehr gut|gut\b)",
    rf"{_DEUTSCH}\w*\s*(?:und|&|,|sowie)\s*englisch\w*\s*[:\-–]?\s*(?:\(|jeweils\s+)?(?:sehr gut|gut\b|flie|verhandlungssicher|in wort und schrift|auf (?:c1|b2)|c1|b2)",
    r"(?:beherrschung|kenntnisse) der deutschen sprache",
    r"deutsche[n]? sprache\s+(?:in wort und schrift|flie|verhandlungssicher|sicher|sehr gut)",
    r"(?:fluent|fluency|proficien\w*|excellent|very good|strong|good|business[- ]fluent|business[- ]level|native|full professional)\s+"
    r"(?:(?:command|knowledge|skills|level|proficiency)\s+(?:of|in)\s+|in\s+|both\s+|business\s+|written and spoken\s+|spoken and written\s+|the\s+|english and\s+|english &\s+)*"
    r"german(?!\s+(?:market|compan|customer|client|law|tax|labou?r|office|team|site|subsidiar|branch|speaking market|start|mittelstand|engineering|automotive|industr))",
    r"german\s*(?:\(|-|:|–|at|level|language)?\s*(?:level\s*)?(?:c1|c2|b2)\b",
    r"german (?:language )?(?:skills )?(?:is |are )?(?:required|mandatory|a must|essential|necessary)",
    r"german and english\s*(?:\(|,|-|–|:)?\s*(?:fluent|c1|both|in word)",
    r"must speak german",
    r"language skills?\s*[:\-–]\s*(?:english\s*(?:&|and|,|und)\s*)?german\b",
    r"basic (?:understanding|knowledge|skills?) (?:in|of) german",
]
_REQ_RX = re.compile("|".join(f"(?:{p})" for p in _REQ), _FLAGS)

_SOFTENER_AFTER = re.compile(r"^.{0,60}?(?:von vorteil|wünschenswert|willkommen|ein plus|plus\b|nice[- ]to[- ]have|advantage|beneficial|desirable|is a bonus|bonus|helpful|preferred|wäre schön|optional)", _FLAGS | re.S)
_SOFTENER_BEFORE = re.compile(r"(?:idealerweise|ideally|optional|nice[- ]to[- ]have:?|preferably|bonus:|plus:)\W+(?:\S+\W+){0,4}$", _FLAGS)

_PLUS = re.compile(
    "|".join([
        rf"{_DEUTSCH}\w*\s+(?:[\w\-/]+\s+){{0,5}}(?:sind |ist |wären |wäre )?(?:von vorteil|wünschenswert|willkommen|ein plus|nice to have)",
        r"german\s*(?:[\w\-/,]+\s+){0,6}(?:is a plus|a plus|nice[- ]to[- ]have|beneficial|advantageous|an advantage|a strong advantage|a big advantage|desirable|welcome|is a bonus|helpful|preferred)",
        r"(?:nice[- ]to[- ]have|bonus|plus)\s*[:\-–]?\s+(?:\S+\s+){0,4}german",
    ]),
    _FLAGS,
)

_NOT_REQ = re.compile(
    "|".join([
        r"(?:no|not|without|kein\w*)\s+(?:\w+\s+){0,2}german\s+(?:\w+\s+){0,2}(?:required|needed|necessary|requirement)",
        r"german (?:skills |language skills |knowledge )?(?:is |are )?not (?:required|necessary|needed|a must|mandatory)",
        r"(?:keine|ohne)\s+(?:\w+\s+)?deutschkenntnisse",
        r"deutschkenntnisse (?:sind )?nicht (?:erforderlich|notwendig|nötig|zwingend)",
        r"english[- ]only",
        r"only english",
        r"(?:working|company|office|team|corporate|business) language (?:is |will be )?english",
        r"english is our (?:working |company |corporate )?language",
        r"arbeitssprache (?:ist )?englisch",
        r"don'?t (?:need to |have to )?speak german",
    ]),
    _FLAGS,
)


# A softener only counts inside the same list item / sentence: in "Sehr gute
# Deutschkenntnisse, gute Englischkenntnisse von Vorteil" the "von Vorteil"
# belongs to English, not German.
_ITEM_SEPARATORS = "\n•;✓✔|"
_OTHER_LANGUAGE = (
    r"(?:englisch|english|französisch|french|spanisch|spanish|italienisch|italian|russisch|russian"
    r"|ukrainisch|ukrainian|polnisch|polish|türkisch|turkish|arabisch|arabic|chinesisch|chinese"
    r"|niederländisch|dutch|portugiesisch|portuguese)"
)
_CLAUSE_END = re.compile(
    rf"[{_ITEM_SEPARATORS}]|\.\s|\s[-*–]\s|,\s*(?:[\w-]+\s+){{0,2}}{_OTHER_LANGUAGE}"
    rf"|\s(?:und|sowie|and|as well as)\s+(?:[\w-]+\s+){{1,2}}{_OTHER_LANGUAGE}"
    r"|(?:weitere|andere|zusätzliche|other|additional|further)\s+(?:fremd)?sprach|(?:other|additional|further)\s+languages",
    _FLAGS,
)


def _clause_after(text, pos):
    window = text[pos: pos + 80]
    m = _CLAUSE_END.search(window)
    return window[: m.start()] if m else window


def _clause_before(text, pos):
    window = text[max(0, pos - 80): pos]
    cut = max([window.rfind(c) for c in _ITEM_SEPARATORS] + [window.rfind(". "), window.rfind(" - "), window.rfind("* ")])
    return window[cut + 1:] if cut >= 0 else window


def german_requirement(text, lang):
    text = text.replace("#", "").replace("**", "")
    hard = False
    soft = False
    for m in _REQ_RX.finditer(text):
        after = _clause_after(text, m.end())
        before = _clause_before(text, m.start())
        if _SOFTENER_AFTER.search(after) or _SOFTENER_BEFORE.search(before):
            soft = True
        else:
            hard = True
            break
    if _NOT_REQ.search(text) and not hard:
        return "none"
    if hard:
        return "required"
    if soft or _PLUS.search(text):
        return "plus"
    if lang == "en":
        return "none"
    return "implicit"


_EN_REQ = re.compile(
    r"(?:flie(?:ß|ss)end\w*|verhandlungssicher\w*|sehr gut\w*|gut\w*|sicher\w*|exzellent\w*|fluent|excellent|very good|good|strong|business)\s+(?:[\w\-/]+\s+){0,3}(?:englisch|english)"
    r"|(?:englisch|english)\w*\s*(?:\(|-|:)?\s*(?:c1|c2|b2)\b"
    r"|(?:englisch|english)\w*\s+(?:in wort und schrift|flie(?:ß|ss)end|verhandlungssicher)",
    _FLAGS,
)


def english_requirement(text, lang):
    if lang == "en":
        return True
    return bool(_EN_REQ.search(text))


# --- Hourly pay ------------------------------------------------------------

_NUM = r"(\d{1,2}(?:[.,]\d{1,2})?)"
_CUR = r"(?:€|eur\b|euro\b|eur\.)"
# "17,50 € brutto pro Stunde", "15 EUR/Std.", "€18 per hour" – marker right after the amount…
_HOURLY_AFTER = re.compile(
    r"^\s*(?:€|eur\w*)?\s*(?:\(?(?:brutto|netto|gross)\)?\s*)?(?:/|pro|per|je|die|an?|the)\s*(?:std\b|std\.|stunde|h\b|hour)"
    r"|^\s*(?:€|eur\w*)?\s*(?:brutto\s*)?(?:stundenlohn|hourly|/h\b|die stunde)",
    _FLAGS,
)
# …or "Stundenlohn von 16 €", "hourly rate of €18" – marker shortly before it.
_HOURLY_BEFORE = re.compile(
    r"(?:stundenlohn|stundensatz|stundenvergütung|stundenentgelt|vergütung pro stunde|hourly (?:rate|wage|pay|salary)|pay per hour)"
    r"\s*(?:\(?(?:brutto|netto|gross)\)?|:|von|in höhe von|i\.\s?h\.\s?v\.|beträgt|liegt bei|zwischen|ab|mindestens|bis zu|of|from|starting at|between|is|\s)*$",
    _FLAGS,
)
_MONEY = re.compile(
    rf"(?:(?:zwischen|between)\s*{_CUR}?\s*{_NUM}\s*{_CUR}?\s*(?:und|and)\s*{_CUR}?\s*{_NUM}\s*{_CUR})"
    rf"|(?:{_CUR}\s*{_NUM}(?:\s*(?:-|–|bis|to)\s*{_CUR}?\s*{_NUM})?)"
    rf"|(?:{_NUM}(?:\s*{_CUR})?\s*(?:-|–|bis|to)\s*{_NUM}\s*{_CUR})"
    rf"|(?:{_NUM}\s*{_CUR})",
    _FLAGS,
)
PAY_MIN, PAY_MAX = 12.0, 60.0


def _f(s):
    return float(s.replace(",", "."))


def hourly_pay_from_text(text):
    """Find '€17,50/Stunde', '15–18 € pro Stunde', 'Stundenlohn von 16 €' etc."""
    found = []
    for m in _MONEY.finditer(text):
        nums = [g for g in m.groups() if g]
        if not nums:
            continue
        # Reject thousands like '1.200 €' (the regex would see '200'): check the char before.
        if m.start() > 0 and text[m.start() - 1] in ".,0123456789":
            continue
        if not (_HOURLY_AFTER.search(text[m.end(): m.end() + 30])
                or _HOURLY_BEFORE.search(text[max(0, m.start() - 50): m.start()])):
            continue
        vals = [_f(n) for n in nums]
        if all(PAY_MIN <= v <= PAY_MAX for v in vals):
            found.append((min(vals), max(vals)))
    if not found:
        return None
    lo = min(f[0] for f in found)
    hi = max(f[1] for f in found)
    if hi > lo * 1.8:  # two unrelated numbers; keep the first mention only
        lo, hi = found[0]
    return lo, hi


def hourly_pay_structured(job):
    """BA's own salary fields. Only hourly values are usable for Werkstudent jobs."""
    if job.get("verguetungsangabe") != "STUNDENLOHN":
        return None
    if job.get("festgehalt"):
        v = float(job["festgehalt"])
        return (v, v) if PAY_MIN <= v <= PAY_MAX else None
    lo, hi = job.get("gehaltsspanneVon"), job.get("gehaltsspanneBis")
    if lo and hi and PAY_MIN <= float(lo) <= float(hi) <= PAY_MAX:
        return float(lo), float(hi)
    return None


# --- Hours per week ----------------------------------------------------------

_HOURS = re.compile(
    r"(\d{1,2})\s*(?:(?:-|–|bis|to)\s*(\d{1,2})\s*)?(?:std\.?|stunden|wochenstunden|hours|h)\s*(?:/|pro|per|in der|a|die|je)?\s*(?:woche|week|wöchentlich|weekly)?",
    _FLAGS,
)


def hours_per_week(text):
    for m in _HOURS.finditer(text):
        ctx = text[m.start(): m.end() + 25].lower()
        if not re.search(r"woche|week|wöchentl|wochenstunden", ctx):
            continue
        vals = [int(g) for g in m.groups() if g]
        if all(8 <= v <= 40 for v in vals):
            return max(vals)
    return None


# --- Study programmes -------------------------------------------------------

MAJORS = [
    ("wiinf", "Wirtschaftsinformatik", r"wirtschafts-?\)?\s?informatik|business informatics|information systems|\bwinf\b"),
    ("inf", "Informatik", r"(?<!wirtschafts)(?<!wirtschafts-)(?<!medien)(?<!bio)(?<!geo)(?<!medizin)informatik|computer science|software engineering|softwaretechnik"),
    ("bwl", "BWL / Economics", r"\bbwl\b|betriebswirtschaft|wirtschaftswissenschaft|business administration|business studies|\beconomics\b|volkswirtschaft|\bvwl\b|international management|business economics|wirtschaftsstudium"),
    ("wiing", "Wirtschaftsingenieurwesen", r"wirtschaftsingenieur|wirtschafts-ingenieur|industrial engineering|\bwi-?ing\b|engineering management"),
    ("mb", "Maschinenbau", r"maschinenbau|mechanical engineering|fahrzeugtechnik|luft- und raumfahrt|aerospace engineering|mechatronik|mechatronics"),
    ("et", "Elektrotechnik", r"elektrotechnik|electrical engineering|elektronik|informationstechnik|electronics"),
    ("math", "Mathe / Statistik / Data Science", r"mathematik|mathematics|statistik|statistics|data science|physik|physics"),
    ("comm", "Kommunikation / Medien / Marketing", r"kommunikationswissenschaft|medienwissenschaft|publizistik|journalismus|journalism|communication studies|medienmanagement|marketingstudium|studium (?:im bereich |der |des )?marketing"),
]
_MAJOR_RX = [(mid, re.compile(rx, _FLAGS)) for mid, _, rx in MAJORS]


def find_majors(text):
    return sorted(mid for mid, rx in _MAJOR_RX if rx.search(text))


# --- Job field ----------------------------------------------------------------

CATEGORIES = [
    ("data", "Data & Analytics", r"\bdata\b|daten(?!schutz)|analytics|analyst|business intelligence|\bbi\b|machine learning|künstliche intelligenz|artificial intelligence|statisti"),
    ("hr", "HR & Recruiting", r"\bhr\b|human resources|\bpersonal(?!\s+(?:assist|trainer|training|shopper|care|banking|finance))|recruit|talent|people (?:&|and) culture|people operations"),
    ("it", "IT & Software", r"software|entwickler|developer|programmier|informatik|frontend|front-end|backend|back-end|full.?stack|devops|cloud|web.?entwickl|webentwickl|cyber|it.?security|it.?sicherheit|\bsap\b|salesforce|netzwerk|network|systemadministr|system engineer|anwendungsentwickl|application|it-support|it support|it-service|it-infrastr|it-projekt|it-consult|digitalisierung|\bapp\b|qa engineer|test engineer|\bqa\b|copilot|azure|m365|rechenzentrum|data cent(?:er|re)|digitali[sz]ation|\btechnology\b"),
    ("finance", "Finance & Controlling", r"financ|finanz|controlling|accounting|buchhalt|kreditor|debitor|bilanz|rechnungswesen|steuer|\btax\b|audit|prüfung|treasury|wirtschaftsprüf|bank|investment|private equity|m&a|corporate finance|risk"),
    ("design", "Design & UX", r"design(?!.{0,10}engineer)|\bux\b|\bui\b|grafik|graphic|video|foto|photo|medien(?:gestalt|produkt)"),
    ("marketing", "Marketing & Communication", r"marketing|social media|content|kommunikation|communication|\bpr\b|presse|seo|brand|redaktion|\beditor|e-commerce|ecommerce|online.?shop|community|influencer|events?\b|eventmanagement"),
    ("retail", "Retail & Hospitality", r"verkäuf|verkauf|einzelhandel|outlet|kassier|kasse|filial|\bstore\b|shop assistant|gastronom|hotel|restaurant|kellner|barista|küche|service-?kraft|servicemitarbeit|lagerhelfer|kommissionier|aushilfe"),
    ("sales", "Sales & Business Development", r"sales|vertrieb|business development|key account|account manag|customer success|kundenbetreuung|kundenberatung|kundenservice|customer service|innendienst|ankauf"),
    ("consulting", "Consulting & Strategy", r"consult|unternehmensberat|strategieberat|managementberat|it-beratung|steuerberat|beratung|strateg"),
    ("product", "Product & Project Mgmt", r"project|projekt|product manag|produktmanag|product owner|pmo|programm.?manag"),
    ("engineering", "Engineering & Production", r"ingenieur|engineering|konstruktion|mechani|elektro|electr|maschinenbau|produktion|production|qualität|quality|fertigung|automotive|fahrzeug|fahrwerk|adas|inbetriebnahme|vehicle|hardware|embedded|energie|energy|bau|architekt|statik|statiker|technik|technisch|technical|anlagen|maschinen|simulation|test(?:ing)?\b|r&d|forschung und entwicklung|verfahrenstechn|robot"),
    ("ops", "Operations & Logistics", r"logistik|logistics|supply chain|einkauf|procurement|purchasing|operations|lager|warehouse|disposition|beschaffung|facility|immobilien|real estate"),
    ("research", "Research & Science", r"forschung|research|labor|\blab\b|chemi|biolog|physik|physics|pharma|klinisch|clinical|wissenschaft"),
    ("education", "Education & Social", r"pädagog|erzieh|lehrer|lehrkraft|tutor|nachhilfe|dozent|sozial|berufsberat|(?<!hoch)schul|kita|betreuer|jugend|teaching|education"),
    ("health", "Health & Care", r"arzt|ärzt|medizin|pflege|therap|apothe|gesundheit|klinik|praxis|health|care\b|rettung|psycholog"),
    ("admin", "Office & Admin", r"assistenz|assistant|office|büro(?:manag|assist|kauf|organisation|arbeit|tätig)|verwaltung|sekretariat|empfang|administration|backoffice|sachbearbeit"),
    ("legal", "Legal", r"\blegal\b|recht|jurist|compliance|datenschutz|privacy"),
]
_CAT_RX = [(cid, re.compile(rx, _FLAGS)) for cid, _, rx in CATEGORIES]
_IT_UPPER = re.compile(r"(?<![A-Za-z])IT(?![a-z])")
# "KI"/"AI" alone says little about the field ("AI Search" in marketing, "KI-Transformation"
# in HR), so it only decides when nothing more specific matched.
_AI = re.compile(r"\bki\b|\bai\b", _FLAGS)


def classify(title, hauptberuf):
    """Assign a job field from the title first, then BA's main occupation."""
    t = re.sub(r"\((?:m|w|d|f|x|div|gn|all genders?|mwd|w/m/d|m/w/d|m/f/d|f/m/d|m/w/x|all)[^)]*\)", " ", title, flags=_FLAGS)
    t = re.sub(r"werkstudent\w*|working student|studentische\w*|aushilfe|minijob", " ", t, flags=_FLAGS)
    for source in (t, hauptberuf or ""):
        if _IT_UPPER.search(source):
            return "it"
        for cid, rx in _CAT_RX:
            if rx.search(source):
                return cid
        if _AI.search(source):
            return "it"
    return "other"


# --- City ----------------------------------------------------------------------

_CITY_FIX = {
    "Frankfurt": "Frankfurt am Main",
    "Frankfurt/Main": "Frankfurt am Main",
    "Frankfurt a. M.": "Frankfurt am Main",
    "Frankfurt a.M.": "Frankfurt am Main",
    "Mainz am Rhein": "Mainz",
    "Muenchen": "München",
    "Koeln": "Köln",
    "Cologne": "Köln",
    "Munich": "München",
    "Nuremberg": "Nürnberg",
    "Halle (Saale)": "Halle",
    "Freiburg im Breisgau": "Freiburg",
    "Offenbach am Main": "Offenbach",
    "Ludwigshafen am Rhein": "Ludwigshafen",
}


def normalise_city(ort):
    if not ort:
        return ""
    c = ort.split(",")[0].strip()
    c = re.sub(r"\s+-\s+.*$", "", c)
    return _CITY_FIX.get(c, c)


# --- Werkstudent filter ---------------------------------------------------------

# Tolerates the common typos "Werksstudent" and "Werkstundent".
_WS = re.compile(r"werk-?s{1,2}tud|werkstund|working[- ]student|work student", _FLAGS)


def is_werkstudent(title):
    return bool(_WS.search(title or ""))


def extract(listing, detail):
    """Combine search listing + detail record into one feature dict."""
    title = listing.get("stellenangebotsTitel") or ""
    text = ""
    if detail:
        text = (detail.get("stellenangebotsBeschreibung") or "")
    full = f"{title}\n{text}"
    lang = posting_language(text or title)

    pay = hourly_pay_structured(listing) or (hourly_pay_structured(detail) if detail else None)
    pay_src = "ba" if pay else ""
    if not pay and text:
        pay = hourly_pay_from_text(full)
        pay_src = "text" if pay else ""

    loc = (listing.get("stellenlokationen") or [{}])[0]
    adr = loc.get("adresse") or {}
    return {
        "category": classify(title, listing.get("hauptberuf")),
        "city": normalise_city(adr.get("ort")),
        "region": adr.get("region") or "",
        "lang": lang,
        "german": german_requirement(full, lang) if text else "",
        "english": int(english_requirement(full, lang)) if text else "",
        "pay_min": f"{pay[0]:.2f}" if pay else "",
        "pay_max": f"{pay[1]:.2f}" if pay else "",
        "pay_src": pay_src,
        "hours": (hours_per_week(full) or "") if text else "",
        "skills": "|".join(find_skills(full)) if text else "",
        "majors": "|".join(find_majors(full)) if text else "",
        "remote": int(bool(listing.get("homeofficemoeglich"))),
        "detail_ok": int(bool(text)),
        "xv": EXTRACTOR_VERSION if text else 0,
    }
