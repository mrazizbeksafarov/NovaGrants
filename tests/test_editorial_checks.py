import pytest

import ai_agent
from editorial_checks import copy_problem, foreign_enrollment_required
from test_sources_and_rich import card, item, configure_ai


@pytest.mark.parametrize("text", [
    "Be a currently-enrolled, full-time undergraduate student at a university located in the United States.",
    "AQShdagi akkreditatsiyalangan davlat yoki xususiy universitetda to'liq vaqtli bakalavr talabasi.",
    "Applicants of all nationalities may apply but must be enrolled in a college in the United States.",
    "Applicants must be enrolled in a university in Canada.",
])
def test_foreign_enrollment_is_not_overridden_by_open_nationality(text):
    assert foreign_enrollment_required(text)


@pytest.mark.parametrize("text", [
    "All nationalities may apply to a summer programme at a university in the United States.",
    "Bakalavr talabalari AQShda sakkiz haftalik tadqiqotda qatnashadi.",
    "Applicants must hold a bachelor's degree. The host university is in Canada.",
])
def test_host_country_is_not_a_residency_restriction(text):
    assert not foreign_enrollment_required(text)


@pytest.mark.parametrize("fields", [
    {"benefits": ["Living stipend $6,000"]},
    {"benefits": ["Hands-on research experience at Stanford Engineering"]},
    {"eligibility": "16–35 yoshdagi O‘zbekiston fuqarosi, yosh mutaxassis"},
])
def test_bad_public_copy_requires_repair(fields):
    assert copy_problem(card(**fields))


def test_source_quote_can_be_english_but_public_copy_is_uzbek():
    assert not copy_problem(card(benefits=["$6,000 stipendiya", "Ilmiy rahbar bilan amaliy tadqiqot"]))


def test_stanford_profile_is_filtered_before_card_is_published():
    g = item(summary="Applicants of all nationalities may apply.")
    content = ai_agent._attach_urls({"cards": [card(eligibility="AQShdagi universitetda kunduzgi bakalavr talabasi")]}, [g])
    assert content["cards"] == []


def test_unverified_amount_is_dropped_from_gemini_copy(monkeypatch):
    configure_ai(monkeypatch, [card(benefits=["Living stipend $6,000", "Tadqiqot xarajatlari qoplanadi"])])
    content = ai_agent.generate_post_content([item()])
    assert content["cards"][0]["benefits"] == ["Tadqiqot xarajatlari qoplanadi"]


def test_gemini_foreign_only_selection_is_an_intentional_exclusion(monkeypatch):
    configure_ai(monkeypatch, [card(eligibility="AQShdagi universitetda kunduzgi bakalavr talabasi")])
    content = ai_agent.generate_post_content([item()])
    assert content is not None and content["cards"] == []
    assert content["audience_excluded_urls"] == [item()["url"]]
