"""Nova Grants must serve applicants currently applying from Uzbekistan."""

from datetime import datetime, timedelta, timezone

import pytest

from filters import looks_like_opportunity, deadline_passed, extract_deadline


@pytest.mark.parametrize("title,summary,expected", [
    ("Winners announced for Global Scholarship", "Eligibility and deadline for the fully funded scholarship were published.", False),
    ("Research Grant for Universities", "Only universities may apply. Funding supports students. Eligibility deadline 2027-01-31.", False),
    ("PhD Fellowship", "Individual doctoral candidates may apply. Host institution confirmation required.", True),
    ("Visiting Research Fellowship", "Postdoctoral researchers may apply. Host institution support required. Fully funded.", True),
    ("Magistratura uchun grant", "Hujjat qabul boshlandi. Bakalavr bitiruvchilari uchun to'liq grant.", True),
    ("Global Scholarship results announced", "A fully funded award with eligibility and application deadline.", False),
    ("Международная стипендия 2027", "Прием заявок открыт.", True),
    ("Grantlar tanlovi boshlandi", "Yoshlar uchun dasturlar ochiq.", True),
    ("Yangi stipendiyalar", "Arizalar qabul qilinmoqda.", True),
    ("Объявлены победители стипендии", "Грант и срок подачи заявок.", False),
])
def test_discovery_filters_preserve_individual_opportunities_and_drop_reports(title, summary, expected):
    assert looks_like_opportunity(title, summary) is expected


def test_reopened_current_call_is_not_closed_by_previous_cycle_text():
    year = datetime.now(timezone.utc).year + 1
    text = f"Applications are closed for {year-1}. Applications are now open for {year}. Deadline: 1 February {year}."
    assert not deadline_passed(text)


def test_ambiguous_numeric_deadline_is_not_guessed():
    year = datetime.now(timezone.utc).year + 1
    assert extract_deadline(f"Deadline: 03/12/{year}") is None
    assert extract_deadline(f"Deadline (MM/DD/YYYY): 03/12/{year}").month == 3


def test_deadline_on_the_following_line_is_retained():
    year = datetime.now(timezone.utc).year + 1
    assert extract_deadline(f"Application deadline:\n18th January {year}").day == 18


def test_later_event_date_does_not_reopen_expired_applications():
    past = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%d")
    future = (datetime.now(timezone.utc) + timedelta(days=60)).strftime("%Y-%m-%d")
    assert deadline_passed(f"Application deadline: {past}; event starts {future}.")


def test_official_catalogue_reads_fresh_details_before_rejecting_old_metadata():
    from filters import discovery_decision
    title = "Global Flourishing Scholarship"
    summary = "Applications are closed. Deadline: 2025-01-01."
    assert discovery_decision(title, summary, refresh_details=True)[0] == "candidate"
    assert discovery_decision(title, summary, refresh_details=False)[0] == "reject"


def test_russian_deadline_and_closed_call_are_not_lost():
    year = datetime.now(timezone.utc).year + 1
    assert extract_deadline(f"Срок подачи заявок: 15 декабря {year}").month == 12
    assert deadline_passed("Приём заявок завершён.")
