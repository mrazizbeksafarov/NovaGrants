"""The owner's Gemini task files opportunities as GitHub issues (nova-inbox)."""

from types import SimpleNamespace

import pytest

import gemini_inbox

BODY = """Bugungi topilmalar:

NOVA-GRANT
**Nomi:** SI Scholarship for Global Professionals 2027/2028
**Havola:** [si.se](https://si.se/en/apply/scholarships/swedish-institute-scholarships-for-global-professionals/)
Muddat: 2027-01-15
Turi: stipendiya
Kimlar: Ish tajribasi bor magistraturaga topshiruvchilar.
Dalil: "Citizens of the following countries are eligible to apply: ... Uzbekistan, Vietnam, Zambia"
Qisqacha: Shvetsiyada magistratura uchun to'liq stipendiya.
END

NOVA-GRANT
Nomi: Aggregator copy
Havola: https://opportunitydesk.org/2026/11/12/some-call/
END

NOVA-GRANT
Nomi: Missing link
Havola: noma'lum
END
"""


def issue(number=1, login="mrazizbeksafarov", body=BODY, created="2020-01-01T02:05:00Z"):
    return {"number": number, "user": {"login": login}, "body": body, "created_at": created,
            "html_url": f"https://github.com/mrazizbeksafarov/NovaGrants/issues/{number}"}


@pytest.fixture
def github(monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY", "mrazizbeksafarov/NovaGrants")
    monkeypatch.setenv("NOVA_INBOX_AUTHORS", "mrazizbeksafarov")
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    calls = {"issues": [issue()], "writes": []}

    def get(url, **kwargs):
        assert kwargs["params"]["labels"] == "nova-inbox"
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: calls["issues"])

    def write(method):
        def send(url, **kwargs):
            calls["writes"].append((method, url, kwargs.get("json")))
            return SimpleNamespace(raise_for_status=lambda: None)
        return send

    monkeypatch.setattr(gemini_inbox.requests, "get", get)
    monkeypatch.setattr(gemini_inbox.requests, "post", write("post"))
    monkeypatch.setattr(gemini_inbox.requests, "patch", write("patch"))
    return calls


def test_parse_reads_markdown_wrapped_fields_and_skips_broken_blocks():
    items = gemini_inbox.parse(BODY)
    assert [i["name"] for i in items] == ["SI Scholarship for Global Professionals 2027/2028", "Aggregator copy"]
    assert items[0]["url"].startswith("https://si.se/en/apply/")
    assert items[0]["deadline"] == "2027-01-15"
    assert "Uzbekistan" in items[0]["evidence"]


def test_fetch_keeps_official_links_and_drops_aggregators(github):
    candidates, issues, problems = gemini_inbox.fetch()
    assert [c["title"] for c in candidates] == ["SI Scholarship for Global Professionals 2027/2028"]
    grant = candidates[0]
    assert grant["source_id"] == gemini_inbox.SOURCE_ID and grant["kind"] == "official"
    assert grant["source_url"].endswith("/issues/1")
    assert "Uzbekistan" in grant["summary"] and "Deadline: 2027-01-15" in grant["summary"]
    assert len(issues) == 1 and problems == []


def test_public_repo_issue_from_a_stranger_is_ignored(github):
    github["issues"] = [issue(login="someone-else")]
    candidates, issues, problems = gemini_inbox.fetch()
    assert candidates == [] and issues == []
    assert "begona" in problems[0]


def test_inbox_is_optional_without_github_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert gemini_inbox.fetch() == ([], [], [])


def test_unreachable_github_is_reported_not_raised(github, monkeypatch):
    def broken(url, **kwargs):
        raise gemini_inbox.requests.ConnectionError("down")
    monkeypatch.setattr(gemini_inbox.requests, "get", broken)
    candidates, issues, problems = gemini_inbox.fetch()
    assert candidates == [] and "o'qilmadi" in problems[0]


def test_finished_issue_is_commented_and_closed(github):
    candidates, issues, _ = gemini_inbox.fetch()
    decisions = [{"url": candidates[0]["url"], "state": "posted", "reason": "ranked_verified_opportunity"}]
    gemini_inbox.finish(issues, candidates, decisions)
    methods = [method for method, *_ in github["writes"]]
    assert methods == ["post", "patch"]
    assert "kanalga chiqdi" in github["writes"][0][2]["body"]
    assert github["writes"][1][2]["state"] == "closed"


def test_issue_with_pending_items_stays_open_for_the_next_run(github, monkeypatch):
    github["issues"] = [issue(created=gemini_inbox.datetime.now(gemini_inbox.timezone.utc).isoformat())]
    candidates, issues, _ = gemini_inbox.fetch()
    gemini_inbox.finish(issues, candidates, [{"url": candidates[0]["url"], "state": "defer", "reason": "digest_limit"}])
    assert github["writes"] == []


def test_stale_issue_closes_even_with_pending_items(github):
    candidates, issues, _ = gemini_inbox.fetch()
    gemini_inbox.finish(issues, candidates, [{"url": candidates[0]["url"], "state": "retry", "reason": "insufficient_evidence"}])
    assert [method for method, *_ in github["writes"]] == ["post", "patch"]
