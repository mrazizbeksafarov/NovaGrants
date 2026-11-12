"""Deterministic checks for the channel's Uzbekistan-based audience and copy."""

import re


def foreign_enrollment_required(text):
    """Foreign study location is a restriction even if nationality is unrestricted."""
    text = re.sub(r"\s+", " ", str(text or "")).casefold()
    country = r"(?:united states|usa|u\.?s\.?|united kingdom|uk|canada|australia)"
    english = (r"(?:must\s+(?:be\s+)?(?:currently\s+)?(?:enrolled|matriculated|studying)"
               r"|currently.enrolled|full.time|matriculated|enrolled)"
               r"[^.!?;\n]{0,180}(?:universit\w*|college)[^.!?;\n]{0,90}"
               r"(?:located in|within|in)\s+(?:the\s+)?" + country + r"\b")
    uzbek = (r"(?:aqsh|kanada|avstraliya|buyuk britaniya)(?:dagi|da)\b"
             r"[^.!?]{0,180}(?:universitet|kollej)[^.!?]{0,120}talaba")
    residence = (r"must\s+(?:(?:already|currently|normally|ordinarily)\s+)?"
                 r"(?:reside|live|be\s+(?:a\s+)?(?:permanent\s+)?resident)\s+(?:in|of)\s+(?:the\s+)?" + country)
    country_before_status = (r"must\s+(?:already\s+)?be\s+(?:a\s+)?" + country
                             + r"\s+(?:permanent\s+)?resident")
    uzbek_residence = (r"(?:aqsh|kanada|avstraliya|buyuk britaniya)(?:da|ning)\s+"
                       r"(?:doimiy|avvaldan)\s+(?:yashovchi|yashash|rezident)")
    return bool(re.search(english, text) or re.search(uzbek, text)
                or re.search(residence, text) or re.search(country_before_status, text)
                or re.search(uzbek_residence, text))


def copy_problem(card):
    """Return a repairable editorial issue, never silently alter requirements."""
    eligibility = str(card.get("eligibility") or "")
    if re.search(r"o[‘’ʻ'`]?zbekiston\s+fuqaro", eligibility, re.I):
        return "Kimlar uchun qismida auditoriya fuqaroligi takrorlangan"
    public = " ".join([str(card.get("summary") or ""), eligibility,
                       *(str(b) for b in card.get("benefits") or []),
                       *(str(b) for b in (card.get("screening") or {}).get("mandatory_costs", []))])
    if re.search(r"\b(?:living stipend|hands.on research|mentoring by|shared accommodation|"
                 r"round.trip (?:airfare|air ticket)|fully funded|all nationalities|application fee|refundable deposit|non.refundable)\b", public, re.I):
        return "Tavsif, foyda yoki talablar tarjima qilinmay qolgan"
    return ""
