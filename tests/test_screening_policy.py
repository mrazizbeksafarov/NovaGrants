import pytest

import ai_agent
import main
import official_evidence
import selection_audit
from post_builder import build_post
from selection_policy import assess, assess_exclusion, established_issuer, priority, stated_application_fee, supported_quote, public_costs
from test_sources_and_rich import card, item
from test_resilient_pipeline import page


def fixture(**facts):
    source, candidate = item(), card()
    candidate["screening"].update(facts)
    return candidate, source


# Two editorial conditions only (2026-11-13): someone in Uzbekistan can apply,
# and the link is the official page. Funding, issuer and quote wording do not veto.
@pytest.mark.parametrize("changes,state,reason", [
    ({}, "publish", "verified_individual_opportunity"),
    ({"uzbekistan": "excluded"}, "reject", "cannot_apply_from_uzbekistan"),
    ({"location": "foreign_required"}, "reject", "cannot_apply_from_uzbekistan"),
    ({"applicant": "institution"}, "reject", "institution_only"),
    ({"call_state": "closed"}, "reject", "closed"),
    ({"funding": "none"}, "publish", "verified_individual_opportunity"),
    ({"uzbekistan": "unclear"}, "publish", "verified_individual_opportunity"),
    ({"location": "unclear"}, "publish", "verified_individual_opportunity"),
    ({"funding": "unclear"}, "publish", "verified_individual_opportunity"),
    ({"scope_quote": "Invented eligibility approval."}, "publish", "verified_individual_opportunity"),
    ({"funding_quote": "Invented full financial coverage."}, "publish", "verified_individual_opportunity"),
    ({"call_quote": "Applications opened on an invented date."}, "publish", "verified_individual_opportunity"),
])
def test_independent_publication_dimensions(changes, state, reason):
    candidate, source = fixture(**changes)
    result = assess(candidate, source)
    assert (result.state, result.reason) == (state, reason)


@pytest.mark.parametrize("url,expected", [
    ("https://www.ox.ac.uk/scholarships", True),
    ("https://engineering.stanford.edu/surf", True),
    ("https://www.daad.de/call", True),
    ("https://www.sussex.ac.uk/funding", True),
    ("https://private-oxford-forum.org", False),
    ("https://ox.ac.uk.fake.example", False),
    ("https://university.edu.fake.example", False),
])
def test_issuer_reputation_does_not_come_from_oxford_in_a_title(url, expected):
    assert established_issuer(url) is expected


def paid_candidate(url="https://private-forum.example/apply", program="conference", organizer="private"):
    candidate, source = fixture(program=program, organizer=organizer, fee="application_fee", fee_amount="$29",
        mandatory_costs=["Qaytarilmaydigan ariza to'lovi: $29."], fee_quote="The application fee is $29 and is non-refundable.")
    source.update(url=url, official_evidence_url=url)
    source["summary"] += " The application fee is $29 and is non-refundable."
    return candidate, source


def test_paid_private_forum_never_auto_publishes_even_when_fully_funded():
    candidate, source = paid_candidate()
    result = assess(candidate, source)
    assert result.state == "review" and result.reason == "paid_private_forum"


def test_established_university_admission_fee_is_evaluated_separately():
    candidate, source = paid_candidate("https://www.ox.ac.uk/funding", "degree_scholarship", "university")
    assert assess(candidate, source).state == "publish"


def test_paid_programme_publishes_with_its_cost_disclosed():
    candidate, source = paid_candidate("https://unknown-university.example/admissions", "degree_scholarship", "university")
    assert assess(candidate, source).state == "publish"
    assert candidate["screening"]["mandatory_costs"]


def test_stated_fee_is_disclosed_even_when_the_model_omits_it():
    candidate, source = paid_candidate("https://www.ox.ac.uk/funding", "degree_scholarship", "university")
    candidate["screening"]["mandatory_costs"] = []
    assert assess(candidate, source).state == "publish"
    assert "to'lov" in candidate["screening"]["mandatory_costs"][0]


def test_known_fee_cannot_be_hidden_by_a_free_label():
    candidate, source = paid_candidate("https://www.ox.ac.uk/funding", "degree_scholarship", "university")
    candidate["screening"].update(fee="none", mandatory_costs=[])
    assert assess(candidate, source).state == "publish"
    assert candidate["screening"]["mandatory_costs"]


def test_refundable_nonprofit_deposit_is_not_a_paid_private_application():
    candidate, source = paid_candidate("https://mcwglobal.org/young-leaders/", "fellowship", "nonprofit")
    source["summary"] = source["summary"].replace("The application fee is $29 and is non-refundable.", "Accepted participants pay a refundable $100 deposit.")
    candidate["screening"].update(fee="refundable_deposit", fee_amount="$100",
        fee_quote="Accepted participants pay a refundable $100 deposit.", mandatory_costs=["Qaytariladigan depozit: $100."])
    assert assess(candidate, source).state == "publish"


@pytest.mark.parametrize("statement", ["Only universities may apply. Funding supports students.", "Only ASEAN nationals may apply.", "All countries except Uzbekistan are eligible."])
def test_model_confirmation_cannot_override_explicit_official_exclusion(statement):
    candidate, source = fixture()
    source["summary"] += " " + statement
    assert assess(candidate, source).state == "reject"


def test_international_students_call_is_open_to_uzbekistan():
    candidate, source = fixture(scope_quote="International students may apply.")
    source["summary"] = "International students may apply. Applications are open."
    assert assess(candidate, source).state == "publish"


def test_call_without_any_applicant_scope_is_not_published():
    candidate, source = fixture(scope_quote="")
    source["summary"] = "Applications are open. Research costs are covered."
    assert assess(candidate, source).reason == "uzbekistan_scope_not_explicit"


def test_plain_individual_profile_on_local_government_call_is_not_lost():
    candidate, source = fixture(scope_quote="16-30 yoshdagi yoshlar qatnashishi mumkin.", funding="free_participation", program="training")
    source.update(url="https://yoshlar.gov.uz/loyiha", official_evidence_url="https://yoshlar.gov.uz/loyiha")
    source["summary"] += " 16-30 yoshdagi yoshlar qatnashishi mumkin."
    assert assess(candidate, source).state == "publish"


def test_invented_stipend_amount_is_removed_not_blocking():
    candidate, source = fixture()
    candidate["benefits"] = ["Oyiga $9,000 stipendiya", "Tadqiqot xarajatlari qoplanadi"]
    assert assess(candidate, source).state == "publish"
    assert candidate["benefits"] == ["Tadqiqot xarajatlari qoplanadi"]


def test_tuition_discount_is_not_advertised_as_a_full_grant():
    candidate, source = fixture(funding="discount")
    candidate["benefits"] = ["To'liq grant", "O'qish to'lovida chegirma"]
    assert assess(candidate, source).state == "publish"
    assert candidate["benefits"] == ["O'qish to'lovida chegirma"]


def test_scholarships_rank_ahead_of_conferences_independently_of_copy_length():
    scholarship = card(screening={**card()["screening"], "program": "degree_scholarship"})
    conference = card(screening={**card()["screening"], "program": "conference"}, summary="Long promotional copy. " * 40)
    assert priority(scholarship) > priority(conference)
    assert main.discovery_priority({"title": "Government Scholarship", "kind": "official"}) > main.discovery_priority({"title": "Scholarship Forum Fully Funded Assembly"})


def test_no_fee_statement_does_not_capture_a_following_stipend_as_a_fee():
    assert not stated_application_fee("No application fee. Participants receive $5,000.")
    assert stated_application_fee("Application processing fee:\n$29, non-refundable.")


def test_literal_funding_list_excerpts_allow_semicolon_separators_not_new_facts():
    text = "International flights are covered.\nAccommodation is provided.\nMeals are included."
    assert supported_quote("International flights are covered; Accommodation is provided; Meals are included.", text)
    assert not supported_quote("International flights are covered; A $9,000 stipend is guaranteed.", text)


def test_costs_remain_visible_outside_collapsed_conditions_in_both_formats():
    candidate = card(conditions=["Qaytariladigan depozit: $100.", "Viza xarajati qoplanmaydi."])
    blocks, html = build_post("Test", [candidate])
    assert any(b["type"] == "paragraph" and "depozit" in str(b) for b in blocks)
    assert "Viza xarajati qoplanmaydi." in html


def test_missing_model_decisions_are_retryable_and_not_silently_skipped():
    content = ai_agent._review_content({"headline": "Empty", "cards": [], "exclusions": []}, [item()], {})
    assert content["rejected_urls"] == [] and content["unverified_urls"] == [item()["url"]]


def test_fabricated_negative_decision_is_not_permanently_rejected():
    result = assess_exclusion({"reason": "not_eligible", "evidence": "Applicants of all nationalities may apply."}, item())
    assert result.state == "review"


def test_paid_private_forum_is_held_before_spending_editorial_quota(monkeypatch):
    g = {**item(), "title": "Private Youth Forum 2027", "url": "https://private-forum.example/apply"}
    raw = "<h1>Eligibility</h1>" + "Applications from all countries are eligible. " * 8 + "Application fee is $29."
    monkeypatch.setattr(official_evidence, "_get", lambda url: page(raw, url))
    result = official_evidence.verify_one(g)
    assert result.status == "review" and result.reason == "paid_private_forum"


def test_official_summary_keeps_country_funding_deadline_and_costs_together():
    from opportunity_content import opportunity_summary
    raw = "<h1>Applications are open</h1>" + "<p>Long programme details.</p>" * 300
    raw += "<h2>Eligibility</h2>" + "<p>Motivation and age requirements.</p>" * 30
    raw += "<p>Open to applicants from all countries and regions worldwide.</p>"
    raw += "<h2>Costs Covered</h2><p>International flights and accommodation are covered.</p>"
    raw += "<p>Accepted participants pay a $100 deposit.</p><h2>Costs Not Covered</h2><p>Visa fees.</p>"
    raw += "<p>Apply on or before December 3, 2027.</p>"
    summary = opportunity_summary(raw,6000)
    for value in ["all countries", "International flights", "$100 deposit", "Visa fees", "December 3"]:
        assert value in summary


def test_audit_trail_does_not_serialize_private_fields():
    selection_audit.reset()
    g = {**item(), "api_key": "private-marker", "summary": "private provider payload"}
    selection_audit.record("policy", g, "review", "paid_private_forum")
    assert "private-marker" not in str(selection_audit.snapshot())
    assert "private provider payload" not in str(selection_audit.snapshot())


def test_cost_label_localisation_preserves_refund_negation_and_amount():
    values = public_costs(["Non-refundable application fee $29", "Refundable deposit $100", "Passport fees", "In-country travel costs"])
    assert "qaytarilmaydigan" in values[0] and "$29" in values[0]
    assert "qaytariladigan depozit" in values[1] and "$100" in values[1]
    assert values[2] == "pasport to'lovi"


def test_new_call_year_at_seen_source_url_is_not_permanently_hidden(monkeypatch):
    import database
    from test_reliability import use_database
    source = item(title="Research Fellowship 2026")
    use_database(monkeypatch, [{"url": source["url"], "url_key": source["url_key"], "source_key": source["source_key"],
                               "title": source["title"], "status": "posted"}])
    assert database.get_seen_source_keys([source["source_key"]]) == {source["source_key"]}
    assert database.get_seen_source_keys([source["source_key"]], {source["source_key"]: "Research Fellowship 2027"}) == set()


def test_new_intake_same_official_url_is_held_as_review_not_silent_duplicate(monkeypatch):
    import database
    from test_reliability import use_database
    old = item(title="Research Fellowship 2026")
    db = use_database(monkeypatch, [{"url": old["url"], "url_key": old["url_key"], "source_key": old["source_key"],
         "title": old["title"], "status": "posted", "fingerprint": "research"}])
    fresh = item(2, title="Research Fellowship 2027", fingerprint="research")
    monkeypatch.setattr(main, "DB_READY", True)
    monkeypatch.setattr(main, "DRY_RUN", False)
    assert main.deduplicate([fresh]) == []
    reviews = [r for r in db.rows if r["status"] == "review"]
    assert len(reviews) == 1
    assert reviews[0]["url"].startswith("urn:novagrants:review:")
    assert db.rows[0]["status"] == "posted" and db.rows[0]["title"] == old["title"]
    assert "new_intake_same_programme_needs_confirmation" in reviews[0]["source_url"]


def test_review_reason_and_evidence_survive_without_overwriting_public_record(monkeypatch):
    import database
    from test_reliability import use_database
    source = item()
    db = use_database(monkeypatch, [{"url": source["url"], "url_key": source["url_key"], "status": "posted"}])
    database.save_review(source, "paid_private_forum")
    database.save_review(source, "mandatory_cost_not_disclosed")
    assert len(db.rows) == 2 and db.rows[0]["status"] == "posted"
    assert db.rows[1]["status"] == "review" and db.rows[1]["reminder_sent"] is True
    assert "mandatory_cost_not_disclosed" in db.rows[1]["source_url"]


def test_old_posted_rows_cannot_bypass_current_reminder_policy(monkeypatch):
    import database
    from test_reliability import use_database
    source = item()
    db = use_database(monkeypatch, [{"url": source["url"], "url_key": source["url_key"], "status": "posted", "reminder_sent": False}])
    monkeypatch.setattr(main, "DRY_RUN", False)
    monkeypatch.setattr(main, "verify_official_pages", lambda rows: [official_evidence.Evidence(source, "ineligible", "foreign_enrolment_required")])
    assert main.revalidate_reminders([source]) == []
    assert db.rows[0]["reminder_sent"] is True and db.rows[0]["status"] == "posted"


def test_unreadable_reminder_evidence_is_not_published_or_marked_sent(monkeypatch):
    import database
    from test_reliability import use_database
    source = item()
    db = use_database(monkeypatch, [{"url": source["url"], "url_key": source["url_key"], "status": "posted", "reminder_sent": False}])
    monkeypatch.setattr(main, "DRY_RUN", False)
    monkeypatch.setattr(main, "verify_official_pages", lambda rows: [official_evidence.Evidence(source, "retry", "site_down")])
    assert main.revalidate_reminders([source]) == []
    assert db.rows[0]["reminder_sent"] is False


def test_unverified_source_date_cannot_create_an_urgent_reminder(monkeypatch):
    source = item()
    monkeypatch.setattr(main, "verify_official_pages", lambda rows: [official_evidence.Evidence(source, "ready")])
    monkeypatch.setattr(main, "generate_post_content", lambda rows: {"cards": [card(_source=source, deadline_iso=None)]})
    assert main.revalidate_reminders([source]) == []


def test_application_fee_stays_visible_when_labelled_a_deposit():
    candidate, source = paid_candidate("https://www.ox.ac.uk/funding", "degree_scholarship", "university")
    candidate["screening"]["fee"] = "refundable_deposit"
    assert assess(candidate, source).state == "publish"
    assert candidate["screening"]["mandatory_costs"]


def test_no_processing_fee_does_not_capture_a_stipend_as_payment():
    assert not stated_application_fee("No application processing fee. Stipend: $6,000.")


def test_currency_substitution_is_not_a_supported_amount():
    from selection_policy import monetary_claims
    assert monetary_claims("A$3,000") != monetary_claims("$3,000")
    assert monetary_claims("6000 CHF") != monetary_claims("9000 CHF")


def test_amount_from_the_official_page_is_kept():
    candidate, source = fixture(funding="partial", funding_quote="Awards provide up to $5,000.")
    source["summary"] += " Awards provide up to $5,000."
    candidate["benefits"] = ["$5,000 gacha yordam"]
    assert assess(candidate, source).state == "publish"
    assert candidate["benefits"] == ["$5,000 gacha yordam"]


@pytest.mark.parametrize("requirement", [
    "Applicants must reside in the United States.",
    "Applicants must be a US permanent resident.",
    "Nomzod AQShning doimiy rezidenti bo'lishi kerak.",
])
def test_existing_foreign_residence_cannot_pass_under_worldwide_nationality(requirement):
    candidate, source = fixture()
    source["summary"] += " " + requirement
    assert assess(candidate, source).state == "reject"


def test_future_overseas_admission_offer_is_not_existing_foreign_residence():
    candidate, source = fixture()
    candidate["eligibility"] = "Bakalavr diplomi va xorijiy OTMdan kelgusida qabul taklifi talab etiladi."
    source["summary"] += " A future host institution offer is required. Individuals may apply from their home country."
    assert assess(candidate, source).state == "publish"


def test_foreign_host_university_does_not_imply_enrolment_there():
    from editorial_checks import foreign_enrollment_required
    assert not foreign_enrollment_required("Applicants must be full-time students at any university; the host university is in Canada.")
    assert not foreign_enrollment_required("Applicants must not reside in the United States.")


def test_full_research_award_ranks_above_a_small_degree_discount():
    full = card(screening={**card()["screening"], "program": "research_fellowship", "funding": "full"})
    discount = card(screening={**card()["screening"], "program": "degree_scholarship", "funding": "discount"})
    assert priority(full) > priority(discount)


def test_paid_unknown_university_is_published_with_costs():
    candidate, source = paid_candidate("https://unknown-college.edu/apply", "degree_scholarship", "university")
    assert assess(candidate, source).state == "publish"


def test_paid_private_forum_cannot_hide_its_type_as_a_scholarship():
    candidate, source = paid_candidate(program="degree_scholarship", organizer="private")
    source.update(title="Private Leadership Forum 2027")
    assert assess(candidate, source).reason == "paid_private_forum"


def test_free_application_claim_is_removed_without_no_fee_evidence():
    candidate, source = fixture(fee="none", fee_quote="")
    source["summary"] = "Applicants of all nationalities may apply. Applications are open."
    candidate["summary"] = "Tadqiqot dasturi. Ariza topshirish bepul."
    assert assess(candidate, source).state == "publish"
    assert candidate["summary"] == "Tadqiqot dasturi."


