"""Regression tests for the 2026-11-13 run: verified calls retried forever.

Run 43381853445 screened 16 official pages and published nothing. Three causes:
inline-span words were split by newlines so verbatim quotes never matched,
country lists on separate eligibility pages were never read, and elided
country-list quotes were rejected outright.
"""

from types import SimpleNamespace

import pytest

import main
import official_evidence
from opportunity_content import opportunity_summary, readable_text
from selection_policy import supported_quote
from bs4 import BeautifulSoup
from test_reliability import grant


def page(html, url=None):
    html = "<main>" + html + "</main>"
    return SimpleNamespace(status_code=200, text=html, content=html.encode(), url=url)


SPAN_SPLIT = ('<p><span>We aim for equal gender repres</span><span>ent</span>'
              '<span>ation among scholarship recipi</span><span>ent</span><span>s.</span></p>'
              '<ul><li>Armenia</li><li>Uzbekistan</li></ul>')


def test_inline_spans_keep_words_whole_and_blocks_separate():
    text = readable_text(BeautifulSoup(SPAN_SPLIT, "html.parser"))
    assert "We aim for equal gender representation among scholarship recipients." in text
    assert "Armenia\nUzbekistan" in text


def test_model_quote_of_span_split_page_is_supported():
    assert supported_quote("equal gender representation among scholarship recipients", opportunity_summary(SPAN_SPLIT))


COUNTRIES = ("Citizens of the following countries are eligible to apply for the SI Scholarship for Global Professionals:\n"
             "Armenia, Azerbaijan, Bangladesh, Belarus*, Bolivia, Ukraine, Uzbekistan, Vietnam, Zambia")


def test_elided_country_list_quote_is_supported():
    assert supported_quote("Citizens of the following countries are eligible to apply for the SI Scholarship "
                           "for Global Professionals: Armenia, … Uzbekistan", COUNTRIES)
    assert supported_quote("Citizens of the following countries are eligible to apply [...] Uzbekistan, Vietnam", COUNTRIES)


@pytest.mark.parametrize("text", [
    "Applicants from all countries are welcome, except citizens of Uzbekistan.",
    "Applicants from all countries are welcome; applicants from Russia are not eligible. Uzbekistan residents apply locally.",
    "Applicants from all countries are welcome. " + "x" * 700 + " Uzbekistan",
])
def test_ellipsis_cannot_hide_a_restriction_or_join_distant_text(text):
    assert not supported_quote("Applicants from all countries are welcome ... Uzbekistan", text)


def test_ellipsis_does_not_allow_invented_fragments():
    assert not supported_quote("Citizens of the following countries are eligible ... Kazakhstan", COUNTRIES)


def test_country_list_on_eligibility_subpage_is_read(monkeypatch):
    g = {**grant(), "url": "https://vliruos.example/get-funded/study-scholarships",
         "title": "ICP Connect Scholarships 2027"}
    calls = []

    def get(url):
        calls.append(url)
        if url.endswith("country-list"):
            return page("<h1>Eligible countries</h1><p>Uzbekistan, Kenya, Peru</p>" + "<p>Country notes.</p>" * 10, url)
        return page('<p>Scholarships for master programmes. Applicants must be nationals of one of the '
                    '<a href="/country-list">25 eligible countries</a>.</p>'
                    '<a href="https://other.example/eligibility">eligibility elsewhere</a>'
                    '<a href="/apply-for-grant">Apply for a grant</a>' + "<p>Programme details.</p>" * 10, url)

    monkeypatch.setattr(official_evidence, "_get", get)
    result = official_evidence.verify_one(g)
    assert result.status == "ready"
    assert calls == [g["url"], "https://vliruos.example/country-list"]
    assert "Uzbekistan" in result.grant["summary"]
    assert result.grant["official_evidence_url"] == g["url"]
    assert result.grant["official_evidence_pages"] == ["https://vliruos.example/country-list"]


def test_page_with_country_scope_does_not_fetch_more(monkeypatch):
    calls = []
    def get(url):
        calls.append(url)
        return page('<p>Applicants of all nationalities may apply.</p><a href="/eligibility">Eligibility</a>'
                    + "<p>Details.</p>" * 20, url)
    monkeypatch.setattr(official_evidence, "_get", get)
    assert official_evidence.verify_one(grant()).status == "ready"
    assert len(calls) == 1


def test_unreadable_eligibility_subpage_keeps_main_evidence(monkeypatch):
    def get(url):
        if url.endswith("/eligibility"):
            return None
        return page('<p>Open to applicants who meet the criteria.</p><a href="/eligibility">Eligibility</a>'
                    + "<p>Details.</p>" * 20, url)
    monkeypatch.setattr(official_evidence, "_get", get)
    result = official_evidence.verify_one(grant())
    assert result.status == "ready" and "official_evidence_pages" not in result.grant


def test_insufficient_evidence_stays_retryable_not_parked(monkeypatch):
    # 2026-11-13: the editor called NED Hurford ("from around the world")
    # insufficient. Parking such answers hid good calls; they stay retryable.
    g = {**grant(), "official_evidence_url": grant()["url"]}
    monkeypatch.setattr(main, "DB_READY", False)
    monkeypatch.setattr(main, "generate_post_content", lambda batch: {
        "cards": [], "unverified_urls": [g["url"]],
        "decisions": [{"url": g["url"], "state": "retry", "reason": "insufficient_evidence"}]})
    held = []
    monkeypatch.setattr(main, "hold_for_review", lambda grant, reason: held.append(reason))
    monkeypatch.setattr(main, "save_grants_batch", lambda rows: None)
    assert main.publish([g]) == 0
    assert held == []


def test_government_agencies_are_established_issuers():
    from selection_policy import established_issuer, paid_issuer_exception
    for url in ["https://si.se/en/apply/scholarships/x/", "https://www.sbfi.admin.ch/en/x"]:
        assert established_issuer(url) and paid_issuer_exception(url)


def test_document_text_keeps_span_split_words(monkeypatch):
    monkeypatch.setattr(official_evidence, "_get", lambda url: page(SPAN_SPLIT + "<p>Details.</p>" * 20, url))
    assert "representation" in official_evidence._document(official_evidence._get("https://x.example/"))[1]


def test_misquoted_evidence_stays_retryable(monkeypatch):
    g = {**grant(), "official_evidence_url": grant()["url"]}
    monkeypatch.setattr(main, "DB_READY", False)
    monkeypatch.setattr(main, "generate_post_content", lambda batch: {
        "cards": [], "unverified_urls": [g["url"]],
        "decisions": [{"url": g["url"], "state": "retry", "reason": "eligibility_quote_unsupported"}]})
    held = []
    monkeypatch.setattr(main, "hold_for_review", lambda grant, reason: held.append(reason))
    monkeypatch.setattr(main, "save_grants_batch", lambda rows: None)
    assert main.publish([g]) == 0
    assert held == []
    assert any("1 ta nomzod" in issue for issue in main.PUBLISH_ISSUES)
