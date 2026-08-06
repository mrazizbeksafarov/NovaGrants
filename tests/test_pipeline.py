"""Nova Grants — quvurning tarmoqsiz (offline) testlari.

Bu yerdagi har bir test JONLI KANALDA SODIR BO'LGAN nosozlikni qaytarib
kelmasligini tekshiradi. Yangi xato topilsa — avval shu yerga test yozing.

    pip install pytest
    pytest -q
"""

import os
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from filters import (
    looks_like_opportunity, extract_deadline, validate_deadline_iso, deadline_passed,
)
from link_resolver import (
    url_key, clean_url, title_fingerprint, is_aggregator, is_blocked,
    link_matches_title, STRONG_ANCHOR_SCORE,
)
from post_builder import build_post, usable_cards, _esc_attr, _deadline_label
from telegram_bot import (
    split_message, utf16_len, sanitize_html, strip_tags_keep_links, _open_tag_stack,
)


def _iso(days_from_now):
    d = datetime.now(timezone.utc) + timedelta(days=days_from_now)
    return d.strftime("%Y-%m-%dT23:59:59Z")


# ══════════════════════════════════════════════════════════════════════════
# filters.py — bu imkoniyatmi yoki yangilikmi
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("title,summary", [
    ("Chevening Scholarships 2027 Now Open", "Deadline: 5 November 2026. Fully funded UK study."),
    ("MEXT Scholarship 2027", "Applications are invited. Apply by 2026-12-15."),
    ("Yangi grant dasturi", "Hujjat qabul boshlandi, oxirgi muddat 30.09.2026"),
    ("DAAD Master's Programme", "Fully funded, open to international students."),
])
def test_haqiqiy_imkoniyat_otadi(title, summary):
    assert looks_like_opportunity(title, summary) is True


@pytest.mark.parametrize("title,summary", [
    ("UK AI chip startup Olix raises €27M", "The company secured a Series B round."),
    ("Winners announced for the Global Youth Prize", "Congratulations to the winners!"),
    ("How to Write a Winning Grant Proposal", "A complete guide for beginners."),
    ("Top 20 Internships in Asia for International Students 2027", "Paid, fully funded."),
    # Jonli kanalda aynan shular sizib o'tgan edi (2026-08-06 auditi):
    ("How I Won a Fully Funded Study Abroad Scholarship and How You Can Too",
     "My journey to a fully funded scholarship."),
    ("17 International Travel, Speaking, Fellowship and Other Opportunities",
     "A roundup of opportunities this week."),
    ("List of Fully Funded Conferences and Youth Summits in 2026",
     "Here are the conferences you can attend."),
])
def test_imkoniyat_emas_tashlanadi(title, summary):
    assert looks_like_opportunity(title, summary) is False


def test_institutsional_grant_tashlanadi():
    assert looks_like_opportunity(
        "NSF Research Grant",
        "Principal investigators at eligible US institutions may apply. "
        "Host institution required.") is False


def test_institutsional_lekin_talabaga_ham_ochiq_otadi():
    assert looks_like_opportunity(
        "PhD Scholarship at Host Institution",
        "Students and PhD candidates may apply for this fully funded fellowship. "
        "Deadline 2026-12-01.") is True


# ── sana ──────────────────────────────────────────────────────────────────
def test_deadline_kontekstdan_topiladi():
    year = datetime.now(timezone.utc).year + 1
    dt = extract_deadline(f"Applications open. Deadline: 15 March {year}. Apply now.")
    assert dt is not None and dt.month == 3 and dt.day == 15


def test_ddmm_va_mmdd_farqlanadi():
    """31/12 faqat DD/MM bo'la oladi; 12/31 faqat MM/DD."""
    year = datetime.now(timezone.utc).year + 1
    a = extract_deadline(f"Deadline 31/12/{year}")
    b = extract_deadline(f"Deadline 12/31/{year}")
    assert a is not None and (a.day, a.month) == (31, 12)
    assert b is not None and (b.day, b.month) == (31, 12)


def test_otib_ketgan_muddat_rad_etiladi():
    """Kanalda 'Oxirgi muddat: 10-avgust, 2024' chiqib qolgan edi."""
    assert validate_deadline_iso("2024-08-10T23:59:59Z") is None
    assert validate_deadline_iso(_iso(30)) is not None


def test_juda_uzoq_muddat_rad_etiladi():
    assert validate_deadline_iso(_iso(1200)) is None


def test_yopilgan_elon_aniqlanadi():
    assert deadline_passed("Applications are closed for this cycle.") is True
    assert deadline_passed("Applications are open.") is False


# ══════════════════════════════════════════════════════════════════════════
# link_resolver.py — havola normallashtirish va moslik
# ══════════════════════════════════════════════════════════════════════════
def test_url_key_bir_xil_grantni_birlashtiradi():
    a = url_key("http://www.Example.com/Grant/?utm_source=rss")
    b = url_key("https://example.com/grant")
    assert a == b == "example.com/grant"


def test_clean_url_tracking_ni_olib_tashlaydi():
    out = clean_url("https://ex.org/a?utm_source=x&id=7&fbclid=zz")
    assert "utm_source" not in out and "fbclid" not in out and "id=7" in out


def test_fingerprint_turli_sarlavhani_birlashtiradi():
    """So'z tartibi, yil va 'fully funded' bezagi izni o'zgartirmasligi kerak."""
    a = title_fingerprint("Erasmus Mundus Joint Master Degree 2027")
    b = title_fingerprint("Joint Master Degree Erasmus Mundus (Fully Funded) 2027")
    assert a and a == b


def test_bir_sozli_sarlavha_izsiz_qoladi():
    """ATAYIN: bitta so'z 'Oxford Scholarship' va 'Oxford Fellowship' ni
    bitta grant deb hisoblab, haqiqiy imkoniyatni yo'q qilardi."""
    assert title_fingerprint("Chevening Scholarship 2026 (Fully Funded)") == ""
    assert title_fingerprint("Apply Now") == ""


def test_turli_grantlar_turli_izga_tushadi():
    a = title_fingerprint("Erasmus Mundus Joint Master Degree")
    b = title_fingerprint("Erasmus Plus Youth Exchange Programme")
    assert a != b


def test_aggregator_va_bloklangan_domenlar():
    assert is_aggregator("https://opportunitydesk.org/2026/x/") is True
    assert is_aggregator("https://www.chevening.org/apply/") is False
    assert is_blocked("https://t.me/some_channel/12") is True
    assert is_blocked("https://sub.facebook.com/x") is True


def test_bosh_sahifa_rad_etiladi():
    ok, reason = link_matches_title("Amaliyot Ofisi dasturi", "https://yoshlar.gov.uz/")
    assert ok is False and "bosh sahifa" in reason


def test_bosh_sahifa_domen_mos_kelsa_qabul():
    ok, _ = link_matches_title("Green Talents Award 2027", "https://greentalents.de/")
    assert ok is True


def test_kuchli_anchor_soz_mosligini_bekor_qiladi():
    """O'zbekcha sarlavha + inglizcha URL: anchor matni yetarli dalil."""
    ok, _ = link_matches_title("Inkubatsiya dasturi", "https://awards.gov.uz/en/pta",
                               anchor_score=STRONG_ANCHOR_SCORE)
    assert ok is True
    ok2, _ = link_matches_title("Inkubatsiya dasturi", "https://awards.gov.uz/en/pta",
                                anchor_score=0)
    assert ok2 is False


# ══════════════════════════════════════════════════════════════════════════
# post_builder.py — post qurish
# ══════════════════════════════════════════════════════════════════════════
def _card(n=1, url=None):
    return {
        "name": f"Grant {n}",
        "url": url or f"https://ex.org/g{n}?a=1&b=2",
        "summary": "Qisqa tavsif.",
        "benefits": ["To'liq grant", "Stipendiya"],
        "eligibility": "Talabalar",
        "deadline_iso": _iso(45),
    }


def test_href_escape_qilinadi():
    """Xom `&` Telegram'da 'can't parse entities' beradi va havola yo'qoladi."""
    _, html = build_post("Sarlavha", [_card()])
    assert "&amp;b=2" in html
    assert "?a=1&b=2" not in html


def test_esc_attr_qoshtirnoqni_yopadi():
    assert '"' not in _esc_attr('https://ex.org/a?q="x"')


def test_takror_havola_bir_marta_chiqadi():
    """AI bitta indexni ikki marta qaytarsa, grant postda ikki marta chiqmasin."""
    cards = [_card(1), _card(1), _card(2)]
    assert len(usable_cards(cards)) == 2


def test_havolasiz_kartochka_tashlanadi():
    assert usable_cards([{"name": "X", "url": ""}]) == []
    assert usable_cards([{"name": "", "url": "https://ex.org"}]) == []
    assert usable_cards([{"name": "X", "url": "javascript:alert(1)"}]) == []


def test_rich_va_html_bir_xil_havolani_beradi():
    blocks, html = build_post("Sarlavha", [_card(1), _card(2)])
    rich_urls = []

    def walk(bs):
        for b in bs:
            t = b.get("text")
            for piece in (t if isinstance(t, list) else [t]):
                if isinstance(piece, dict) and piece.get("type") == "url":
                    rich_urls.append(piece["url"])
            for key in ("blocks",):
                if isinstance(b.get(key), list):
                    walk(b[key])
            for item in b.get("items", []) or []:
                walk(item.get("blocks", []))

    walk(blocks)
    assert len(rich_urls) == 2
    for u in rich_urls:
        assert _esc_attr(u) in html


def test_deadline_ozbekcha_yoziladi():
    assert _deadline_label("2026-11-05T23:59:59Z") == "5-noyabr, 2026"
    assert _deadline_label("") == ""


# ══════════════════════════════════════════════════════════════════════════
# telegram_bot.py — bo'lish, teglar, zaxira yo'l
# ══════════════════════════════════════════════════════════════════════════
def test_uzun_post_bolinganda_teglar_butun_qoladi():
    demo = "\n\n".join(
        f"<b>Grant {i}</b>\n<i>Tavsif.</i>\n"
        f'<a href="https://ex.org/g{i}">Ariza topshirish</a>'
        for i in range(1, 121))
    parts = split_message(demo, limit=2000)
    assert len(parts) > 1
    for p in parts:
        assert p.count("<a ") == p.count("</a>")
        assert p.count("<b>") == p.count("</b>")
        assert utf16_len(p) <= 2000 + 200          # qayta ochilgan teglar uchun zaxira
        assert _open_tag_stack(p) == []


def test_qisqa_post_bolinmaydi():
    assert split_message("<b>Salom</b>") == ["<b>Salom</b>"]


def test_sanitize_faqat_ruxsat_etilgan_teglarni_qoldiradi():
    out = sanitize_html('<b>qoladi</b><script>alert(1)</script><div>x</div>'
                        '<a href="#">havola</a>')
    assert "<b>" in out and "<a " in out
    assert "<script>" not in out and "<div>" not in out


def test_zaxira_yol_havolani_yoqotmaydi():
    """HTML xatosida teglar o'chadi, LEKIN havola matnda qolishi shart."""
    html = ('<b>Grant</b>\n<a href="https://ex.org/apply?a=1&amp;b=2">'
            'Ariza topshirish</a>')
    out = strip_tags_keep_links(html)
    assert "<" not in out
    assert "https://ex.org/apply?a=1&b=2" in out
    assert "Ariza topshirish" in out


def test_utf16_emoji_ikki_birlik():
    assert utf16_len("ab") == 2
    assert utf16_len("🎓") == 2
