"""Nomzodlarni saralash: bu haqiqiy ochiq imkoniyatmi yoki shunchaki yangilikmi?

Bu bosqich AI dan OLDIN ishlaydi. Maqsad — Gemini ga yuborilayotgan ro'yxatni
tozalash: yangiliklar, reklama va muddati o'tgan e'lonlar shu yerda tushib qoladi.
Shu tufayli AI arzonroq ishlaydi va kanalga axlat tushmaydi.
"""

import re
from datetime import datetime, timezone, timedelta

# Ochiq imkoniyatga ishora qiluvchi so'zlar (inglizcha + o'zbekcha + ruscha)
POSITIVE = re.compile(
    r"\b("
    r"scholarship|scholarships|scholars|grant|grants|fellowship|fellowships|fellow"
    r"|bursary|stipend"
    r"|fully[\s-]funded|full[\s-]funded|funded|funding|tuition|assistantship"
    r"|call\s+for\s+(applications?|proposals?|papers?|nominations?)"
    r"|applications?\s+(are\s+)?(open|invited|now\s+open)|apply\s+now|now\s+accepting"
    r"|internship|traineeship|exchange\s+program|summer\s+school|winter\s+school"
    r"|competition|contest|olympiad|hackathon|challenge|award|prize"
    r"|accelerator|incubator|pre-?seed|residency|mobility\s+program"
    r"|phd\s+position|postdoc|masters?\s+program|undergraduate\s+program"
    r"|erasmus|chevening|fulbright|daad|mext|gks|vlir|nuffic|humphrey|mandela\s+washington"
    # o'zbekcha
    r"|grant\w*|stipendiya\w*|ariza\w*|tanlov\w*|musobaqa\w*|konkurs\w*|imkoniyat\w*|dastur\w*|amaliyot\w*"
    r"|hujjat\s+qabul|qabul\s+boshlandi|ro'yxatdan\s+o'tish|bepul\s+ta'lim"
    # ruscha
    r"|стипенди\w*|грант\w*|конкурс\w*|заявк\w*|обучени\w*|бесплатн\w*|стажировк\w*"
    r")\b",
    re.I,
)

# Yangilik/reklama belgilari — ochiq chaqiruv emas
NEGATIVE = re.compile(
    r"("
    r"raise[sd]?\s+\$|raises\s+€|secures\s+\$|closes\s+\$?\d+.{0,10}(round|funding)"
    r"|series\s+[a-e]\b|seed\s+round|funding\s+round|valuation|acquire[sd]?\b|acquisition"
    # DIQQAT: \bipo\b — ikkala tomonda ham chegara SHART.
    # Aks holda "WIPO" (Butunjahon intellektual mulk tashkiloti) ham ushlanib,
    # uning barcha amaliyot va fellowship e'lonlari yo'qoladi.
    r"|\bipo\b|merger|layoffs?|appoints?\b|steps?\s+down|resigns?\b|partners?\s+with"
    r"|launches\s+new\s+(feature|product|app)|announces\s+partnership"
    r"|webinar\s+(recap|replay)|recap\b|highlights\s+from|thank\s+you\s+for\s+attending"
    r"|winners?\s+announced|congratulations\s+to|meet\s+the\s+(winners|cohort)"
    r"|has\s+(been\s+)?closed|applications?\s+(are\s+)?closed|deadline\s+(has\s+)?passed"
    r"|sotuv|chegirma|reklama|obuna\s+bo'ling|kanalimizga"
    # o'zbekcha "natija/tabrik" e'lonlari — bular imkoniyat emas, hisobot
    r"|natijalar[i]?\s+e'lon\s+qilindi|natijalari\s+ma'lum|g'oliblar\s+aniqlandi"
    r"|tabriklaymiz|muvaffaqiyatli\s+(o'tkazildi|yakunlandi)|yakunlandi\b"
    r"|qabul\s+qilingan\s+talabalarimiz|erishdi\b"
    r")",
    re.I,
)

# O'zbekistonlik yosh uchun aniq qimmatli imkoniyat belgilari.
# Sarlavhada signal bo'lmasa ham, shulardan biri uchrasa yozuvni saqlab qolamiz —
# aynan shu ro'yxat Schwarzman, Knight-Hennessy kabi grantlarning tushib
# qolishining oldini oladi (ularning sarlavhasi shunchaki dastur nomi bo'ladi).
HIGH_VALUE = re.compile(
    r"("
    r"fully[\s-]funded|full\s+scholarship|tuition\s+(waiver|free|covered|fee\s+waiver)"
    r"|chevening|fulbright|erasmus|daad|mext|\bgks\b|schwarzman|rhodes\s+scholar"
    r"|gates\s+cambridge|knight[\s-]?hennessy|yenching|humphrey|mandela\s+washington"
    r"|open\s+to\s+all\s+nationalities|all\s+nationalities|international\s+students"
    r"|developing\s+countries|worldwide|no\s+application\s+fee"
    r"|to'liq\s+grant|to‘liq\s+grant|toʻliq\s+grant|to'liq\s+moliyalash|bepul\s+ta'lim"
    r"|100%\s*grant|full\s+grant"
    r")",
    re.I,
)

# Jismoniy shaxs emas, TASHKILOT topshiradigan grantlar (NSF, UKRI, ERC uslubi).
# O'zbekistonlik talaba yoki yosh mutaxassis bularga ariza topshira olmaydi.
INSTITUTIONAL_ONLY = re.compile(
    r"("
    r"principal\s+investigator|\bco-?PI\b|host\s+institution|lead\s+(applicant\s+)?organi[sz]ation"
    r"|eligible\s+(organi[sz]ations|institutions|applicants\s+are\s+(universities|institutions))"
    r"|research\s+organi[sz]ations\s+(may|can|are)|only\s+(universities|institutions|organi[sz]ations)"
    r"|uk-?based\s+(organi[sz]ations|researchers|institutions)|us-?based\s+(institutions|organi[sz]ations)"
    r"|accredited\s+institution|consortium\s+of\s+(at\s+least|partners)"
    r"|state\s+(agencies|governments)\s+(may|are)|nonprofits?\s+(may|are\s+eligible\s+to)\s+apply"
    r"|institutions\s+of\s+higher\s+education\s+(may|are)"
    r")",
    re.I,
)

# Jismoniy shaxsga qaratilganini bildiruvchi signal — yuqoridagini bekor qiladi
INDIVIDUAL_SIGNAL = re.compile(
    r"(students?|applicants?\s+must\s+be|young\s+(people|professionals|leaders)|youth"
    r"|candidates?\s+(must|should)|individuals?\s+(may|can|are\s+invited)"
    r"|bachelor|master|undergraduate|postgraduate|phd\s+(student|candidate|position)"
    r"|age\s+(limit|between|of)|aged?\s+\d{2}[\s-]|under\s+\d{2}\s+years"
    r"|talaba|yosh(lar)?|nomzod|ishtirokchi)",
    re.I,
)

# Grant emas, "kontent": namuna hujjatlar, qo'llanmalar va ro'yxat-maqolalar.
# Bularda bitta aniq ariza havolasi bo'lmaydi — kanalga tushishi mumkin emas.
NOT_AN_OPPORTUNITY = re.compile(
    r"("
    r"sample\s+(grant\s+)?proposal|proposal\s+(template|sample|example)|template\s+for"
    r"|how\s+to\s+(write|apply|prepare|get|find)|guide\s+to\b|a\s+complete\s+guide"
    r"|tips\s+(for|to)\b|everything\s+you\s+need\s+to\s+know|what\s+is\s+a\b"
    r"|top\s+\d+\s|best\s+\d+\s|\d+\s+(best|top)\s|list\s+of\s+\d+"
    r"|frequently\s+asked|faq\b|glossary|checklist"
    r"|qanday\s+(qilib|yozish)|qo'llanma|namuna\s+hujjat"
    # ── 2026-08-06 auditida sizib o'tgani aniqlangan shakllar ────────────
    # "How I Won a Fully Funded Study Abroad Scholarship and How You Can Too"
    # — shaxsiy hikoya, ariza sahifasi yo'q. Eski naqsh faqat "how to" ni
    # ushlardi.
    r"|how\s+i\s+(won|got|landed|secured|earned)|my\s+(journey|story|experience)\s+"
    r"|success\s+stor(y|ies)|what\s+i\s+learned"
    # "17 International Travel, Speaking, Fellowship and Other Opportunities"
    # — to'plam maqolasi. Sarlavha raqam bilan boshlanadi va ko'plikda tugaydi.
    r"|^\s*\d{1,3}\s+[a-z].{0,60}\b(opportunities|scholarships|fellowships"
    r"|internships|grants|programs|programmes|conferences|jobs)\b"
    r"|list\s+of\s+(fully|top|best|the)|round[\s-]?up\b|weekly\s+digest"
    r"|opportunities\s+(of|for)\s+the\s+week"
    r")",
    re.I,
)

# "Ariza topshirish" bilan bog'liq aniq signal — kuchli ishonch beradi
STRONG = re.compile(
    r"(deadline|apply\s+by|application\s+deadline|closing\s+date|last\s+date"
    r"|eligibility|eligible\s+(candidates|applicants|countries)|how\s+to\s+apply"
    r"|oxirgi\s+muddat|muddat|talablar|kimlar\s+ishtirok)",
    re.I,
)

# An old winners report does not become an open call by mentioning a deadline.
RESULT_TITLE = re.compile(
    r"winners?\s+announced|results?\s+(?:announced|published)|congratulations\s+to"
    r"|meet\s+the\s+(?:winners|cohort)|natijalar\w*\s+(?:e.lon|ma.lum)"
    r"|g.oliblar\s+aniqlandi|tabriklaymiz|(?:объявлены|опубликованы)\s+(?:результаты|победители)"
    r"|победители\s+(?:объявлены|определены)|поздравляем", re.I)
ORG_APPLICATION_ONLY = re.compile(
    r"only\s+(?:eligible\s+|registered\s+)?(?:universities|institutions|organi[sz]ations|nonprofits?|consortia)"
    r"\s+(?:may|can|are\s+eligible\s+to)\s+apply"
    r"|applications?\s+must\s+be\s+submitted\s+by\s+(?:universities|organi[sz]ations|institutions)", re.I)
PERSON_APPLICATION = re.compile(
    r"(?:individuals?|students?|doctoral\s+candidates?|postdoctoral\s+researchers?|researchers?|scientists?|artists?|entrepreneurs?)"
    r"(?:\s+(?:applicants?|candidates?))?\s+(?:may|can|are\s+eligible\s+to)\s+apply", re.I)
OPEN_CALL = re.compile(
    r"applications?\s+(?:are\s+)?(?:now\s+|currently\s+)?(?:open|reopened)\b"
    r"|qabul\s+(?:boshlandi|qayta\s+ochildi)|при[её]м\s+заявок\s+открыт|снова\s+принимаются\s+заявки", re.I)

# Sanani matndan topish uchun naqshlar
_MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9, "october": 10, "oct": 10,
    "november": 11, "nov": 11, "december": 12, "dec": 12,
    "yanvar": 1, "fevral": 2, "mart": 3, "aprel": 4, "may": 5,
    "iyun": 6, "iyul": 7, "avgust": 8, "sentabr": 9, "sentyabr": 9,
    "oktabr": 10, "oktyabr": 10, "noyabr": 11, "dekabr": 12,
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
    "июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}
_DATE_PATTERNS = [
    # 31 December 2026 / 31 Dec, 2026
    re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?(?:\s+|\s*[-–]\s*)([a-zа-яё]{3,9})[,\s]+(\d{4})\b", re.I),
    # December 31, 2026 / Dec 31 2026
    re.compile(r"\b([a-z]{3,9})\s+(\d{1,2})(?:st|nd|rd|th)?[,\s]+(\d{4})\b", re.I),
    # 2026-12-31
    re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"),
    # 31/12/2026 yoki 31.12.2026
    re.compile(r"\b(\d{1,2})[./](\d{1,2})[./](\d{4})\b"),
]
_DEADLINE_CONTEXT = re.compile(
    r"(deadline|apply\s+by|closing\s+date|closes\s+on|last\s+date|due\s+(by|date)"
    r"|application[s]?\s+close|on\s+or\s+before|oxirgi\s+muddat|muddat|срок\s+подачи(?:\s+заявок)?|крайний\s+срок|при[её]м\s+заявок\s+до)[\s:–-]*[^\n]{0,100}",
    re.I,
)


def opportunity_filter_reason(title: str, summary: str, topic: str = "") -> str:
    """Bu yozuv ochiq imkoniyatga o'xshaydimi?"""
    text = f"{title}\n{summary}"

    # Qo'llanma / namuna / "Top 20" ro'yxati — sarlavhada bo'lsa darrov rad etamiz
    if NOT_AN_OPPORTUNITY.search(title or ""):
        return "not_an_open_individual_opportunity"
    if RESULT_TITLE.search(title or ""):
        return "not_an_open_individual_opportunity"
    if ORG_APPLICATION_ONLY.search(text) and not PERSON_APPLICATION.search(text):
        return "not_an_open_individual_opportunity"

    # Tashkilotlar uchun grant — jismoniy shaxsga ishora bo'lmasa rad etamiz
    if INSTITUTIONAL_ONLY.search(text) and not (INDIVIDUAL_SIGNAL.search(text) or PERSON_APPLICATION.search(text)):
        return "not_an_open_individual_opportunity"

    if NEGATIVE.search(text):
        # Salbiy signal bor — faqat juda kuchli ijobiy signal bo'lsa o'tkazamiz
        return "" if STRONG.search(text) and POSITIVE.search(text) else "news_or_marketing"

    if not POSITIVE.search(text):
        return "not_an_open_individual_opportunity"

    if POSITIVE.search(title or ""):
        return ""

    # Sarlavhada signal yo'q. Telegram postlarida sarlavha ko'pincha emoji yoki
    # qisqa gap bo'ladi, shuning uchun tanadagi dalilga qaraymiz. Quyidagilardan
    # BIRORTASI yetarli:
    #   • ariza/muddat/talab haqida aniq gap (STRONG)
    #   • "to'liq grant", "fully funded", nufuzli dastur nomi (HIGH_VALUE)
    #   • imkoniyat so'zlari kamida ikki xil joyda uchrashi
    if STRONG.search(text) or HIGH_VALUE.search(text):
        return ""

    return "" if len(set(m.group(0).lower() for m in POSITIVE.finditer(text))) >= 2 else "weak_opportunity_signal"


def looks_like_opportunity(title: str, summary: str, topic: str = "") -> bool:
    return not opportunity_filter_reason(title, summary, topic)


def discovery_decision(title, summary, topic="", refresh_details=False):
    if refresh_details and POSITIVE.search(title or "") and not RESULT_TITLE.search(title or ""):
        return "candidate", "needs_fresh_official_details"
    if deadline_passed(f"{title}\n{summary}"):
        return "reject", "expired_secondary_announcement"
    reason = opportunity_filter_reason(title, summary, topic)
    return ("reject", reason) if reason else ("candidate", "needs_official_verification")


def _try_build(y, m, d):
    try:
        if not (1 <= m <= 12 and 1 <= d <= 31):
            return None
        return datetime(y, m, d, 23, 59, 59, tzinfo=timezone.utc)
    except ValueError:
        return None


def extract_deadline(text: str, *, include_past: bool = False):
    """Matndan oxirgi muddatni topadi. Topilmasa None.

    Faqat muddat kontekstidagi sanani oladi; tadbir boshlanish sanasi deadline emas.
    include_past=True eskirgan e'lonlarni aniqlash uchun eng so'nggi muddatni beradi.
    """
    if not text:
        return None

    now = datetime.now(timezone.utc)
    horizon = now + timedelta(days=730)          # 2 yildan uzoq sanalar shubhali

    def scan(chunk):
        found = []
        for pat in _DATE_PATTERNS:
            for m in pat.finditer(chunk):
                g = m.groups()
                dt = None
                if pat is _DATE_PATTERNS[0]:
                    mon = _MONTHS.get(g[1].lower())
                    if mon:
                        dt = _try_build(int(g[2]), mon, int(g[0]))
                elif pat is _DATE_PATTERNS[1]:
                    mon = _MONTHS.get(g[0].lower())
                    if mon:
                        dt = _try_build(int(g[2]), mon, int(g[1]))
                elif pat is _DATE_PATTERNS[2]:
                    dt = _try_build(int(g[0]), int(g[1]), int(g[2]))
                else:
                    # 31/12/2026 va 12/31/2026 — ikkalasi ham uchraydi.
                    # Ilgari doim DD/MM deb o'qilardi, ya'ni amerikacha
                    # manbalarda sana noto'g'ri chiqardi (03/12 -> 3-dekabr,
                    # aslida 12-mart). Endi qaysi raqam 12 dan katta ekaniga
                    # qarab hal qilamiz; ikkalasi ham <=12 bo'lsa xalqaro
                    # ko'rinish (DD/MM) ustun, chunki manbalarimiz asosan
                    # Yevropa va Osiyodan.
                    a, b, year = int(g[0]), int(g[1]), int(g[2])
                    if a > 12 >= b:
                        dt = _try_build(year, b, a)          # DD/MM
                    elif b > 12 >= a:
                        dt = _try_build(year, a, b)          # MM/DD
                    elif a == b:
                        dt = _try_build(year, b, a)
                    elif re.search(r"DD/MM|DD.MM", chunk, re.I):
                        dt = _try_build(year, b, a)
                    elif re.search(r"MM/DD|MM.DD", chunk, re.I):
                        dt = _try_build(year, a, b)
                    # Otherwise ambiguous numeric dates stay unknown.
                if dt and (include_past or now <= dt) and dt <= horizon:
                    found.append(dt)
        return found

    # 1) "deadline ..." atrofidagi sanalar ustuvor
    contexts = [re.split(r"\b(?:event\s+(?:starts?|dates?)|programme?\s+(?:starts?|begins?|dates?)|course\s+starts?)\b",
                         m.group(0), maxsplit=1, flags=re.I)[0]
                for m in _DEADLINE_CONTEXT.finditer(text)]
    hits = [dt for ctx in contexts for dt in scan(ctx)]
    if not hits:
        return None
    return max(hits) if include_past else min(hits)


def validate_deadline_iso(iso):
    """AI bergan muddatni tekshiradi. Ishonchsiz bo'lsa None qaytaradi.

    Kanalda "Oxirgi muddat: 10-avgust, 2024" chiqib qolgan edi — AI yilni
    noto'g'ri o'qigan va hech kim tekshirmagan. Endi o'tib ketgan yoki juda
    uzoq sanalar rad etiladi.
    """
    if not iso or not isinstance(iso, str) or len(iso) < 10:
        return None

    value = iso.strip()
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            dt = datetime.fromisoformat(value).replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
        else:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(timezone.utc)
    except ValueError:
        return None

    now = datetime.now(timezone.utc)
    if dt < now:
        return None                              # o'tib ketgan
    if dt > now + timedelta(days=900):
        return None                              # ~2.5 yildan uzoq — shubhali
    return dt.isoformat().replace("+00:00", "Z")


def deadline_passed(text: str) -> bool:
    """Matnda faqat o'tib ketgan sana bo'lsa True (ya'ni e'lon eskirgan)."""
    if not text:
        return False
    if (re.search(r"(applications?\s+(are\s+)?closed|deadline\s+(has\s+)?passed|muddat\s+tugagan|при[её]м\s+заявок\s+(?:заверш[её]н|закрыт)|заявки\s+не\s+принимаются)", text, re.I)
            and not OPEN_CALL.search(text)):
        return True
    deadline = extract_deadline(text, include_past=True)
    now = datetime.now(timezone.utc)
    ambiguous = []
    for context in _DEADLINE_CONTEXT.finditer(text):
        chunk = re.split(r"\b(?:event\s+(?:starts?|dates?)|programme?\s+(?:starts?|begins?|dates?)|course\s+starts?)\b",
                         context.group(0), maxsplit=1, flags=re.I)[0]
        if re.search(r"DD/MM|DD.MM|MM/DD|MM.DD", chunk, re.I):
            continue
        for match in _DATE_PATTERNS[3].finditer(chunk):
            a, b, year = map(int, match.groups())
            if 1 <= a <= 12 and 1 <= b <= 12 and a != b:
                ambiguous.extend(dt for dt in (_try_build(year, a, b), _try_build(year, b, a)) if dt)
    # Both interpretations must have expired; never guess one numeric format
    # and discard a call that may still be open under the other interpretation.
    if ambiguous and max(ambiguous) >= now:
        return False
    return bool((deadline and deadline < now) or (ambiguous and max(ambiguous) < now))


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    samples = [
        ("Chevening Scholarships 2027 Now Open", "Deadline: 5 November 2026. Fully funded UK study."),
        ("UK AI chip startup Olix raises €27M", "The company secured a Series B round led by..."),
        ("Winners announced for the Global Youth Prize", "Congratulations to the winners!"),
        ("MEXT Scholarship 2027", "Applications are invited. Apply by 2026-12-15."),
        ("Yangi grant dasturi e'lon qilindi", "Hujjat qabul boshlandi, oxirgi muddat 30.09.2026"),
    ]
    for t, s in samples:
        print(f"{'✅' if looks_like_opportunity(t, s) else '❌'}  {t}")
        print(f"     muddat: {extract_deadline(t + ' ' + s)}")
