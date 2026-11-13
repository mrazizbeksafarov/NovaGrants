"""Nova Grants publication policy, separate from model wording and discovery."""

from dataclasses import dataclass
from datetime import datetime, timezone
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from typing import Literal, Optional

from pydantic import BaseModel, Field

from editorial_checks import foreign_enrollment_required
from filters import deadline_passed
from link_resolver import host_of


class Screening(BaseModel):
    uzbekistan: Literal["confirmed", "excluded", "unclear"] = Field(description="Can a person currently living/studying in Uzbekistan apply? Nationality alone does not override residence/work authorization requirements.")
    applicant: Literal["individual", "institution", "unclear"]
    location: Literal["no_foreign_prerequisite", "foreign_required", "unclear"] = Field(description="Existing foreign residence/enrolment/work permission, not the future destination. A future admission/host offer can be obtained from Uzbekistan.")
    call_state: Literal["open", "closed", "unclear"]
    program: Literal["degree_scholarship", "research_fellowship", "fellowship", "internship", "exchange", "summer_school", "competition", "accelerator", "training", "conference", "other"] = Field(description="A leadership/community fellowship is fellowship, not a research fellowship or an employment internship.")
    funding: Literal["full", "tuition_only", "partial", "stipend", "discount", "prize", "free_participation", "none", "unclear"]
    organizer: Literal["government", "university", "intergovernmental", "nonprofit", "private", "unclear"]
    fee: Literal["none", "admission_fee", "application_fee", "refundable_deposit", "participation_fee", "unclear"] = Field(description="Known mandatory charge. A stated refundable deposit is refundable_deposit, even if an application fee is not mentioned. none needs explicit no-fee evidence; absence is unclear.")
    fee_amount: Optional[str] = Field(default=None, description="Exact mandatory amount and currency, or null when not stated. Do not infer free application from an omitted fee.")
    mandatory_costs: list[str] = Field(default_factory=list, description="POSTDA KO'RINADIGAN MATN, FAQAT O'ZBEKCHA. Translate Passport fees = Pasport to'lovi; Visa fees = Viza to'lovi; refundable deposit = qaytariladigan depozit; non-refundable = qaytarilmaydi. Include all mandatory costs and reimbursement conditions, do NOT copy English source wording here.")
    scope_quote: str = Field(default="", description="Verbatim source evidence for eligibility from Uzbekistan; not a translation or a generic benefits claim. Empty if unknown.")
    funding_quote: str = Field(default="", description="Verbatim source evidence for the type of financial benefit. A tuition discount is not full funding. Empty if unknown.")
    call_quote: str = Field(default="", description="Verbatim evidence that applications are open, rolling or have a current future deadline. Empty if unknown.")
    fee_quote: str = Field(default="", description="Verbatim fee/deposit/excluded-cost evidence when present; empty if not stated.")


class Exclusion(BaseModel):
    index: int = Field(strict=True, ge=1)
    reason: Literal["not_eligible", "institution_only", "closed", "not_opportunity", "self_funded", "insufficient_evidence", "paid_private_forum"]
    evidence: str = Field(default="", description="Verbatim source quote supporting this decision. Missing information is insufficient_evidence, not a permanent rejection. Empty if unavailable.")


@dataclass(frozen=True)
class Decision:
    state: str  # publish, reject, review, retry
    reason: str


ACADEMIC = {"ethz.ch", "epfl.ch", "unilu.ch", "lu.se", "su.se", "kth.se", "helsinki.fi", "aalto.fi", "uni-bonn.de", "hu-berlin.de", "mpg.de", "embl.org", "cern.ch", "oist.jp"}
PUBLIC = {"daad.de", "chevening.org", "stipendiumhungaricum.hu", "turkiyeburslari.gov.tr", "studyinnl.org", "eyuf.uz", "un.org", "undp.org", "unicef.org", "unesco.org", "unhcr.org", "worldbank.org", "europa.eu"}
PAID_ACADEMIC = ACADEMIC | {"ox.ac.uk", "cam.ac.uk", "harvard.edu", "mit.edu", "stanford.edu", "yale.edu", "princeton.edu", "imperial.ac.uk", "ucl.ac.uk", "sussex.ac.uk", "kaust.edu.sa", "kaist.ac.kr", "u-tokyo.ac.jp", "nus.edu.sg", "ntu.edu.sg"}
EVENT = re.compile(r"forum|summit|sammit|assembly|conference|konferensiya|symposium|форум|саммит|конференц|симпозиум", re.I)


def _belongs(host, domains):
    return any(host == domain or host.endswith("." + domain) for domain in domains)


def established_issuer(url):
    host = host_of(url).lower()
    academic = bool(re.search(r"(?:\.edu|\.ac\.[a-z]{2}|\.edu\.[a-z]{2})$", host)) or _belongs(host, ACADEMIC)
    public = bool(re.search(r"(?:\.gov|\.gov\.[a-z]{2}|\.go\.[a-z]{2})$", host)) or _belongs(host, PUBLIC)
    return academic or public


def paid_issuer_exception(url):
    host = host_of(url).lower()
    return bool(re.search(r"(?:\.gov|\.gov\.[a-z]{2}|\.go\.[a-z]{2})$", host)) or _belongs(host, PUBLIC | PAID_ACADEMIC)


def normalized(text):
    value = unicodedata.normalize("NFKC", str(text or ""))
    value = value.translate(str.maketrans({"’": "'", "‘": "'", "ʻ": "'", "ʼ": "'", "–": "-", "—": "-", "‑": "-", "‐": "-"}))
    value = re.sub(r"\s*-\s*", "-", value)
    return re.sub(r"\s+", " ", value).strip().casefold()


ELLIPSIS = re.compile(r"\s*\[?\.{3}\]?\s*")  # "…" is NFKC-normalized to "..."
ELLIPSIS_GAP_LIMIT = 600
# An elided span must not be able to hide a restriction ("all countries ...
# Uzbekistan" cut out of "all countries except Uzbekistan").
RESTRICTIVE_GAP = re.compile(r"\b(?:not|no|except|excluding|exclude[ds]?|ineligible|cannot|can't|only|unless|other than|but)\b")


def supported_quote(quote, text):
    quote, text = normalized(quote), normalized(text)
    if len(quote) < 8:
        return False
    if quote in text:
        return True
    # Models separate genuine list-item excerpts with semicolons, and shorten
    # long country lists with an ellipsis ("Citizens of ... : Armenia, ...,
    # Uzbekistan"). Accept only ordered verbatim fragments; an elided gap must
    # be short and free of negation, so a removed "except"/"not" never passes.
    pieces = []
    for elided_before, chunk in enumerate(ELLIPSIS.split(quote)):
        for position, part in enumerate(chunk.split(";")):
            part = part.strip().strip(",:").rstrip(".").strip()
            if part:
                pieces.append((part, bool(elided_before) and position == 0))
    shortest = 5 if any(elided for _, elided in pieces) else 8
    if len(pieces) < 2 or any(len(part) < shortest for part, _ in pieces):
        return False
    cursor = None
    for part, elided in pieces:
        index = text.find(part, cursor or 0)
        if index < 0:
            return False
        if elided and cursor is not None:
            gap = text[cursor:index]
            if len(gap) > ELLIPSIS_GAP_LIMIT or RESTRICTIVE_GAP.search(gap):
                return False
        cursor = index + len(part)
    return True


def public_costs(items):
    """Localize common cost labels without changing amounts or refund negation."""
    replacements = [
        (r"\bnon[-‑– ]refundable\b", "qaytarilmaydigan"),
        (r"\brefundable deposit\b", "qaytariladigan depozit"),
        (r"\bpassport fees?\b", "pasport to'lovi"),
        (r"\bvisa fees?\b", "viza to'lovi"),
        (r"\bapplication (?:processing )?fee\b", "ariza to'lovi"),
        (r"\bin[-‑– ]country\b", "mamlakat ichidagi"),
        (r"\btravel costs?\b", "safar xarajatlari"),
        (r"\bairport transfer\b", "aeroportga borish va qaytish"),
        (r"\bextra baggage\b", "qo'shimcha bagaj"),
        (r"\bpassport\b", "pasport"),
    ]
    out = []
    for item in items:
        text = str(item)
        for pattern, translation in replacements:
            text = re.sub(pattern, translation, text, flags=re.I)
        out.append(text)
    return out


def stated_application_fee(text):
    value = normalized(text)
    for match in re.finditer(r"(?:application(?:\s+processing)?|processing|participation|registration|admission)\s+fee", value):
        before = value[max(0, match.start()-15):match.start()]
        after = value[match.end():match.end()+180]
        if re.search(r"(?:no|without|zero)\s*$", before) or re.match(r"\s+(?:is\s+)?(?:not required|not charged|waived for all|zero)\b", after):
            continue
        if re.search(r"[$€£]\s*\d|\d[\d., ]*\s*(?:usd|eur|gbp)\b", after):
            return True
    return False


def monetary_claims(text):
    currencies = {"$": "USD", "£": "GBP", "€": "EUR", "usd": "USD", "gbp": "GBP", "eur": "EUR",
                  "aqsh dollari": "USD", "dollar": "USD", "funt": "GBP", "yevro": "EUR"}
    codes = "USD EUR GBP CHF AUD CAD NZD SGD HKD JPY CNY KRW INR RUB AED SAR QAR UZS KZT TRY MYR THB PLN SEK NOK DKK".split()
    currencies.update({code.lower(): code for code in codes})
    currencies.update({"us$": "USD", "au$": "AUD", "a$": "AUD", "c$": "CAD", "s$": "SGD", "hk$": "HKD", "₩": "KRW"})
    found = set()
    patterns = [(r"(US\$|AU\$|HK\$|A\$|C\$|S\$|[$£€₩]|" + "|".join(codes) + r")\s*(\d[\d,]*(?:\.\d+)?)", False),
                (r"(\d[\d,]*(?:\.\d+)?)\s*(" + "|".join(codes) + r"|AQSh dollari|dollar|funt|yevro)\b", True)]
    for pattern, reverse in patterns:
        for match in re.finditer(pattern, str(text or ""), re.I):
            currency, amount = (match[2], match[1]) if reverse else (match[1], match[2])
            try:
                found.add((currencies.get(currency.lower(), currencies.get(currency)), Decimal(amount.replace(",", ""))))
            except InvalidOperation:
                continue
    return found


def assess(card, source):
    from filters import ORG_APPLICATION_ONLY, PERSON_APPLICATION, RESULT_TITLE, NOT_AN_OPPORTUNITY
    raw = card.get("screening")
    if not raw:
        return Decision("retry", "screening_missing")
    screening = Screening.model_validate(raw).model_dump()
    text = normalized(source.get("summary"))
    if ORG_APPLICATION_ONLY.search(text) and not PERSON_APPLICATION.search(text):
        return Decision("reject", "institution_only")
    if ORG_APPLICATION_ONLY.search(text) and PERSON_APPLICATION.search(text):
        return Decision("review", "mixed_applicant_routes")
    if RESULT_TITLE.search(source.get("title", "")) or NOT_AN_OPPORTUNITY.search(source.get("title", "")):
        return Decision("reject", "not_opportunity")
    if re.search(r"(?:only|exclusively)\s+(?:US citizens|African (?:citizens|nationals)|Nigerian (?:citizens|students)|ASEAN nationals|EU citizens|US permanent residents)", text, re.I):
        return Decision("reject", "foreign_citizenship_only")
    if re.search(r"(?:except|excluding|not open to)[^.!?]{0,160}uzbekistan|uzbekistan[^.!?]{0,80}(?:not eligible|ineligible|excluded)", text, re.I):
        return Decision("reject", "uzbekistan_explicitly_excluded")
    if any(screening[key] == "unclear" for key in ("uzbekistan", "applicant", "location", "call_state", "funding")):
        return Decision("review", "eligibility_or_funding_unclear")
    for key in ("scope_quote", "funding_quote", "call_quote"):
        if not supported_quote(screening[key], text):
            return Decision("retry", f"{key}_unsupported")
    explicit_scope = re.search(r"uzbek|o.zbek|all (?:nationalities|countries)|any (?:nationality|country)|worldwide|around the world|central asia|markaziy osiyo|non[-\s](?:EU|EEA)|outside (?:the )?(?:EU|EEA)|узбек|ўзбек|всех стран|любой страны|центральн\w*\s+ази", screening["scope_quote"], re.I)
    evidence_host = host_of(source.get("official_evidence_url") or source.get("url", ""))
    local_scope = evidence_host.endswith((".gov.uz",)) or evidence_host in {"gov.uz", "eyuf.uz", "it-park.uz"}
    if not explicit_scope and not local_scope:
        return Decision("review", "uzbekistan_scope_not_explicit")
    if screening["fee_quote"] and not supported_quote(screening["fee_quote"], text):
        return Decision("retry", "fee_quote_unsupported")
    if screening["applicant"] == "institution":
        return Decision("reject", "institution_only")
    if screening["uzbekistan"] == "excluded" or screening["location"] == "foreign_required":
        return Decision("reject", "cannot_apply_from_uzbekistan")
    if foreign_enrollment_required(str(source.get("summary") or "") + " " + str(card.get("eligibility") or "")):
        return Decision("reject", "foreign_enrolment_required")
    if screening["call_state"] == "closed" or deadline_passed(source.get("summary", "")):
        return Decision("reject", "closed")
    if screening["funding"] == "none":
        return Decision("reject", "self_funded")
    fee_signal = stated_application_fee(source.get("summary", ""))
    # A model's "none" must not erase a stated fee on the official page.
    if fee_signal and screening["fee"] not in {"admission_fee", "application_fee", "participation_fee"}:
        return Decision("review", "fee_contradiction")
    paid = fee_signal or screening["fee"] in {"admission_fee", "application_fee", "participation_fee"}
    trusted = established_issuer(source.get("official_evidence_url") or source.get("url", ""))
    event = screening["program"] == "conference" or EVENT.search(source.get("title", ""))
    if event and (paid or screening["fee"] == "unclear"):
        if not trusted or screening["organizer"] in {"private", "nonprofit", "unclear"}:
            return Decision("review", "paid_private_forum")
    if event and not trusted:
        return Decision("review", "event_issuer_needs_review")
    if screening["program"] == "other":
        return Decision("review", "programme_type_unclear")
    if paid and not paid_issuer_exception(source.get("official_evidence_url") or source.get("url", "")):
        return Decision("review", "unestablished_paid_programme")
    if screening["fee"] in {"admission_fee", "application_fee", "participation_fee", "refundable_deposit"}:
        if not screening["mandatory_costs"] or not screening["fee_quote"]:
            return Decision("review", "mandatory_cost_not_disclosed")
    public = " ".join([card.get("summary", ""), *card.get("benefits", []), *screening["mandatory_costs"]])
    evidence = screening["funding_quote"] + " " + screening["fee_quote"]
    if not monetary_claims(public).issubset(monetary_claims(evidence)):
        return Decision("review", "financial_amount_unsupported")
    if screening["fee_amount"] and not monetary_claims(screening["fee_amount"]).issubset(monetary_claims(screening["fee_quote"])):
        return Decision("review", "fee_amount_unsupported")
    if (monetary_claims(public) and re.search(r"up to|at most|maximum", screening["funding_quote"], re.I)
            and not re.search(r"gacha|eng ko.pi|maksimal|ko.pi bilan", public, re.I)):
        return Decision("review", "conditional_amount_omitted")
    if re.search(r"ariza\w*\s+(?:topshirish\s+)?bepul", public, re.I):
        free_quote = re.search(r"(?:no|without|zero)\s+(?:application\s+|processing\s+)?fee|application\s+(?:is\s+)?free|waived for all|ariza\w*\s+(?:topshirish\s+)?bepul|to.lov\s+(?:olinmaydi|yo.q|undirilmaydi)|(?:сбор|плата|взнос)[^.\n]{0,40}не взимается|бесплатная подача", screening["fee_quote"], re.I)
        if screening["fee"] != "none" or not free_quote:
            return Decision("review", "free_application_unsupported")
    if screening["funding"] in {"discount", "partial", "tuition_only"} and re.search(r"to[‘’ʻ'`]?liq\s+grant|barcha\s+xarajatlar\s+qoplanadi", public, re.I):
        return Decision("review", "full_funding_overclaimed")
    return Decision("publish", "verified_individual_opportunity")


def discovery_priority(grant):
    title = str(grant.get("title") or "").lower()
    if EVENT.search(title):
        value = 1
    elif re.search(r"scholarship|stipendi|chevening|mext|erasmus|gks|fulbright|bursari|burslary", title):
        value = 6
    elif re.search(r"research|fellowship|phd|doktor|postdoc|internship|amaliyot", title):
        value = 5
    elif re.search(r"exchange|competition|hackathon|accelerator|almashuv|tanlov", title):
        value = 4
    elif re.search(r"summer.school|winter.camp|summer.camp|training|yozgi.maktab|trening", title):
        value = 3
    elif re.search(r"forum|summit|assembly|conference|symposium", title):
        value = 1
    else:
        value = 2
    trusted = established_issuer(grant.get("official_evidence_url") or grant.get("url", ""))
    return (value, trusted or grant.get("kind") == "official")


def cycle_hint(title):
    years = [int(y) for y in re.findall(r"\b20\d{2}\b", str(title or ""))]
    return min(years) if years else None


def assess_exclusion(exclusion, source):
    from filters import ORG_APPLICATION_ONLY, PERSON_APPLICATION, RESULT_TITLE, NOT_AN_OPPORTUNITY
    reason = exclusion["reason"]
    if reason == "insufficient_evidence":
        return Decision("retry", reason)
    evidence = exclusion.get("evidence", "")
    if len(evidence.strip()) < 8 or normalized(evidence) not in normalized(source.get("summary")):
        return Decision("retry", "exclusion_quote_unsupported")
    if reason == "paid_private_forum":
        return Decision("review", reason)
    if reason == "closed" and deadline_passed(source.get("summary", "")):
        return Decision("reject", reason)
    if reason == "institution_only" and ORG_APPLICATION_ONLY.search(evidence) and not PERSON_APPLICATION.search(evidence):
        return Decision("reject", reason)
    if reason == "not_opportunity" and (RESULT_TITLE.search(source.get("title", "")) or NOT_AN_OPPORTUNITY.search(source.get("title", ""))):
        return Decision("reject", reason)
    if reason == "self_funded" and re.search(r"self.funded|no financial support|participants?\s+(?:must\s+)?(?:pay|cover)\s+(?:all|their own)", evidence, re.I):
        return Decision("reject", reason)
    if reason == "not_eligible" and (foreign_enrollment_required(evidence) or re.search(r"(?:only|exclusively|restricted to).{0,50}(?:US citizens|African|Nigerian|ASEAN|EU citizens|permanent residents)", evidence, re.I)):
        return Decision("reject", reason)
    return Decision("review", "unconfirmed_rejection")


def priority(card):
    screening = card.get("screening") or {}
    program = {"degree_scholarship": 6, "research_fellowship": 5, "internship": 5, "fellowship": 4, "exchange": 4,
               "competition": 4, "accelerator": 4, "summer_school": 3, "training": 2, "conference": 1}
    funding = {"full": 5, "stipend": 4, "tuition_only": 3, "partial": 3, "prize": 3, "discount": 1, "free_participation": 1}
    source = card.get("_source") or {}
    issuer = established_issuer(source.get("official_evidence_url") or card.get("url", ""))
    urgency = 0
    try:
        date = datetime.fromisoformat(str(card.get("deadline_iso", "")).replace("Z", "+00:00"))
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        urgency = int(0 <= (date - datetime.now(timezone.utc)).days <= 14)
    except ValueError:
        pass
    program_value = program.get(screening.get("program"), 0)
    funding_value = funding.get(screening.get("funding"), 0)
    return (4 * program_value + 6 * funding_value + 2 * issuer, funding_value, program_value, urgency)
