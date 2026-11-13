"""Global-source, selection-quality and Bot API 10.4 regressions."""

import json
from types import SimpleNamespace

import pytest
import requests

import ai_agent
import link_resolver
import main
import scraper
import telegram_bot
from opportunity_content import opportunity_summary
from post_builder import build_post
from rich_schema import validate_blocks, rich_usage
from sources import SOURCES, enabled_sources
from tools.check_sources import inspect_feed


def item(n=1, **fields):
    return {"title": "ETH Student Summer Research Fellowship 2027", "source_id": f"source-{n}",
            "url": "https://inf.ethz.ch/studies/summer-research-fellowship.html",
            "url_key": "inf.ethz.ch/studies/summer-research-fellowship.html",
            "source_url": f"https://news.example/post/{n}", "source_key": f"news.example/post/{n}",
            "summary": "Applicants of all nationalities may apply. Applications are open. All research costs are covered. No application fee is charged.", **fields}


def card(**fields):
    return {"index": 1, "name": "ETH Research Fellowship", "summary": "Moliyalashtiriladigan tadqiqot dasturi.",
            "url": item()["url"], "eligibility": "Bakalavr bosqichining so'nggi kursida o'qiyotgan talabalar",
            "eligibility_evidence": "Applicants of all nationalities may apply.",
            "screening": {"uzbekistan": "confirmed", "applicant": "individual", "location": "no_foreign_prerequisite", "call_state": "open",
                          "program": "research_fellowship", "funding": "full", "organizer": "university", "fee": "none", "fee_amount": None,
                          "mandatory_costs": [], "scope_quote": "Applicants of all nationalities may apply.", "funding_quote": "All research costs are covered.",
                          "call_quote": "Applications are open.", "fee_quote": "No application fee is charged."},
            "deadline_iso": "2027-12-15T23:59:59Z", **fields}


def test_new_aggregators_always_require_original_links():
    ids = [s["id"] for s in SOURCES]
    assert len(ids) == len(set(ids))
    for src in enabled_sources():
        if src["kind"] == "aggregator" and src["type"] == "rss":
            assert link_resolver.is_aggregator(src["url"]), src["id"]
        if src.get("max_age_days", 60) is None:
            assert src["kind"] == "official" and src["fetch_details"]
    channels = {s["channel"] for s in enabled_sources() if s["type"] == "telegram"}
    assert "elyurtumidifoundation" in channels and "innovatsion_rivojlanish" in channels
    assert "eyuf_uz" not in channels and "mininnovation" not in channels


def test_summary_keeps_eligibility_and_deadline_at_end_of_long_article():
    raw = "<p>International study opportunity.</p>" + "<p>Long introduction.</p>" * 100
    raw += "<h2>Eligibility criteria</h2><p>Applicants of all nationalities may apply.</p>"
    raw += "<h2>Application deadline</h2><p>15 December 2027</p>"
    text = opportunity_summary(raw)
    assert "all nationalities" in text and "15 December 2027" in text
    assert len(text) <= 1800


def test_summary_keeps_nationality_exclusion_not_just_international_intro():
    raw = "<p>International Scholarship.</p>" + "<p>Benefits.</p>" * 200
    raw += "<h2>Eligibility</h2><p>Only citizens and residents of Nigeria are eligible.</p>"
    assert "Only citizens and residents of Nigeria" in opportunity_summary(raw)


def test_feed_html_links_can_resolve_without_fetching_aggregator(monkeypatch):
    g = item(url="https://opportunitiespedia.com/eth-fellowship/")
    g["feed_html"] = f'<p>Details</p><a href="{item()["url"]}">Official website</a>'
    visited = []
    monkeypatch.setattr(link_resolver, "follow_redirects", lambda url: visited.append(url) or url)
    result = link_resolver.resolve_grant(g)
    assert result["url"] == item()["url"]
    assert visited == [item()["url"]]


def test_feed_shortcut_does_not_accept_aggregators(monkeypatch):
    g = item(url="https://opportunitiespedia.com/eth/")
    g["feed_html"] = '<a href="https://fullyscholarships.com/eth/">Apply now</a>'
    monkeypatch.setattr(link_resolver, "find_original_link", lambda url, **kwargs: ("", 0))
    monkeypatch.setattr(link_resolver, "_get", lambda *args: None)
    assert link_resolver.resolve_grant(g)["url"] == ""


def test_program_named_after_sponsor_can_link_to_host_university():
    assert link_resolver.link_matches_title(
        "SSRP Amgen Scholars Program 2027", "https://biosciences.stanford.edu/pathways/ssrp-amgen-scholars-program/",
        link_resolver.STRONG_ANCHOR_SCORE)[0]


def test_submit_portal_does_not_create_mit_program_identity():
    fingerprint = link_resolver.program_fingerprint("Global Youth Fellowship", "https://submittable.com/submit")
    assert not fingerprint.startswith("mit")


def test_same_host_rss_http_links_are_upgraded_to_https(monkeypatch):
    entry = {"title": "Global Scholarship", "link": "http://university.example/scholarships/1", "summary": "All nationalities"}
    monkeypatch.setattr(scraper, "_fetch_feed", lambda *args: SimpleNamespace(entries=[entry]))
    results = scraper.scrape_rss({"id": "official", "url": "https://university.example/feed/", "kind": "official"})
    assert results[0]["url"] == "https://university.example/scholarships/1"


def test_resolver_checks_second_candidate_when_first_is_unrelated(monkeypatch):
    html = '<article><p>Research opportunity.</p><a href="https://gatescambridge.org/apply/">Apply now</a><a href="https://imperial.ac.uk/study/phd-scholarships/">Official website</a></article>'
    monkeypatch.setattr(link_resolver, "_get", lambda *args: SimpleNamespace(status_code=200, text=html))
    monkeypatch.setattr(link_resolver, "follow_redirects", lambda url: url)
    url, _ = link_resolver.find_original_link("https://opportunitydesk.org/imperial/", "Imperial College PhD Scholarships")
    assert url.startswith("https://imperial.ac.uk/")


def test_weak_anchor_with_program_specific_path_is_usable(monkeypatch):
    g = item(title="Lingnan University Hong Kong PhD Fellowship Scheme 2027",
             url="https://youthbreaktheboundaries.com/lingnan/")
    official = "https://www.ln.edu.hk/rpg/hong-kong-phd-fellowship-scheme-hkpfs"
    g["feed_html"] = f'<a href="{official}">Hong Kong PhD Fellowship Scheme at Lingnan University</a>'
    monkeypatch.setattr(link_resolver, "follow_redirects", lambda url: url)
    assert link_resolver.resolve_grant(g)["url"] == official


def test_official_catalogue_requires_detail_page(monkeypatch):
    g = item(fetch_details=True, detail_selector="#main")
    monkeypatch.setattr(link_resolver, "_get", lambda *args: None)
    assert link_resolver.resolve_grant(g)["url"] == ""


def test_official_detail_supplies_eligibility_to_editor(monkeypatch):
    g = item(fetch_details=True, detail_selector="#main")
    response = SimpleNamespace(status_code=200, url=g["url"], text='<div id="main"><h2>Eligibility</h2><p>All nationalities may apply.</p></div>')
    monkeypatch.setattr(link_resolver, "_get", lambda *args: response)
    result = link_resolver.resolve_grant(g)
    assert "All nationalities may apply" in result["summary"]


def test_http_200_html_is_not_a_working_feed():
    assert inspect_feed(b"<html>Cloud protection page</html>", {})["status"] == "EMPTY_OR_NOT_FEED"


def test_source_check_detects_stale_rss():
    raw = b'<rss version="2.0"><channel><title>Feed</title><item><title>Grant</title><link>https://example.org/apply</link><pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate></item></channel></rss>'
    assert inspect_feed(raw, {})["status"] == "STALE"
    assert inspect_feed(raw, {"max_age_days": None})["date_policy"] == "live_details"


def test_duplicate_representative_keeps_richer_eligibility(monkeypatch):
    monkeypatch.setattr(main, "DB_READY", False)
    sparse = item(1, summary="Research fellowship.")
    rich = item(2)
    unique = main.deduplicate([sparse, rich])
    assert len(unique) == 1 and unique[0]["source_id"] == "source-2"
    assert unique[0]["_aliases"][0]["source_key"] == sparse["source_key"]


def test_same_generic_title_at_unrelated_institutions_is_not_merged(monkeypatch):
    monkeypatch.setattr(main, "DB_READY", False)
    grants = [item(i, title="Global Youth Fellowship", url=f"https://{host}/apply",
                   url_key=f"{host}/apply", fingerprint="same-title")
              for i, host in enumerate(["alpha.example", "beta.example"], 1)]
    assert len(main.deduplicate(grants)) == 2


def test_bridging_source_connects_prior_duplicate_groups(monkeypatch):
    monkeypatch.setattr(main, "DB_READY", False)
    a = item(1, title="Alpha Leadership Award", url="https://awards.example/alpha", url_key="awards.example/alpha", fingerprint="alpha")
    b = item(2, title="Beta Leadership Award", url="https://awards.example/beta", url_key="awards.example/beta", fingerprint="beta")
    bridge = item(3, title="Bridging Award", url=a["url"], url_key=a["url_key"], fingerprint="beta")
    unique = main.deduplicate([a, b, bridge])
    assert len(unique) == 1 and len(unique[0]["_aliases"]) == 2


def test_database_fingerprint_is_scoped_to_its_institution(monkeypatch):
    import database
    from test_reliability import FakeDatabase
    db = FakeDatabase([{"url": "https://alpha.example/apply", "url_key": "alpha.example/apply",
                        "fingerprint": "same-title", "status": "posted"}])
    monkeypatch.setattr(database, "supabase", db)
    assert database.get_seen_fingerprint_scopes(["same-title"]) == {("same-title", "alpha.example")}


def configure_ai(monkeypatch, cards):
    response = SimpleNamespace(text=json.dumps({"headline": "New opportunities", "cards": cards}), usage_metadata=None)
    cli = SimpleNamespace(models=SimpleNamespace(generate_content=lambda **kwargs: response))
    monkeypatch.setattr(ai_agent, "API_KEYS", ["test"])
    monkeypatch.setattr(ai_agent, "MAX_ATTEMPTS", 1)
    monkeypatch.setattr(ai_agent, "get_client", lambda *args: cli)


def test_current_models_and_supported_thinking_are_used(monkeypatch):
    assert all(not name.startswith("gemini-2.") for name in ai_agent.MODEL_CHAIN)
    monkeypatch.setattr(ai_agent, "THINKING_LEVEL", "minimal")
    cfg = ai_agent._config_for("gemini-3.8-flash")
    assert str(cfg.thinking_config.thinking_level).lower().endswith("low")
    assert cfg.temperature is None


def test_editor_scope_comes_from_the_official_page_not_the_model(monkeypatch):
    source = item(summary="Applications are open. All research costs are covered.")
    configure_ai(monkeypatch, [card(eligibility_evidence="Uzbekistan is explicitly eligible.",
                                    screening={**card()["screening"], "scope_quote": "Uzbekistan is explicitly eligible."})])
    content = ai_agent.generate_post_content([source])
    assert content is None or content["cards"] == []


def test_editor_accepts_supported_eligibility_quote(monkeypatch):
    configure_ai(monkeypatch, [card()])
    assert ai_agent.generate_post_content([item()])["cards"][0]["url"] == item()["url"]


def test_editor_receives_evidence_beyond_old_700_character_cutoff():
    summary = "Long introduction. " * 60 + "All nationalities including Uzbekistan may apply."
    assert "Uzbekistan" in ai_agent._build_prompt([item(summary=summary)])


def test_modern_rich_design_has_one_application_action():
    blocks, html = build_post("New opportunities", [card()])
    assert validate_blocks(blocks) == []
    buttons = next(b["buttons"] for b in blocks if b["type"] == "buttons")
    assert buttons[0]["style"] == "primary" and buttons[0]["url"] == item()["url"]
    assert len(buttons) == 1
    assert "copy_text" not in str(blocks)
    assert not any("custom_emoji" in str(b) for b in blocks)
    assert item()["url"] in html
    # The main rich card has one URL action, not a duplicate text link below it.
    assert not any(b["type"] == "paragraph" and "'type': 'url'" in str(b) for b in blocks)
    assert blocks[0] == {"type": "photo", "photo": {"type": "photo", "media": "attach://nova_cover"}}


def test_deadline_is_visible_outside_collapsed_details():
    blocks, _ = build_post("New", [card(benefits=["Funding"])])
    deadline = next(b for b in blocks if b["type"] == "paragraph" and "Muddat: " in str(b))
    assert "15-dekabr, 2027" in str(deadline)
    assert str(deadline).count("15-dekabr, 2027") == 1
    assert "date_time" not in str(deadline)
    assert all("date_time" not in str(b) for b in blocks if b["type"] == "details")


def test_unknown_deadline_is_explicit_and_not_inferred():
    blocks, html = build_post("New", [card(deadline_iso=None)])
    assert any(b["type"] == "footer" and b["text"] == "Muddat ko'rsatilmagan" for b in blocks)
    assert "Muddat ko'rsatilmagan" in html


def test_collapsed_eligibility_does_not_lose_critical_final_condition():
    requirements = "Additional academic requirements. " * 15 + "Applicants must reside in Uzbekistan."
    blocks, html = build_post("New", [card(eligibility=requirements)])
    assert "Applicants must reside in Uzbekistan." in str(blocks)
    assert "Applicants must reside in Uzbekistan." in html


def test_long_url_remains_available_as_application_button():
    blocks, _ = build_post("New", [card(url="https://example.org/apply?token=" + "x" * 300)])
    assert validate_blocks(blocks) == []
    assert len(next(b["buttons"] for b in blocks if b["type"] == "buttons")) == 1


@pytest.mark.parametrize("bad", [
    [{"type": "paragraph", "text": {"type": "customemoji", "text": "x"}}],
    [{"type": "buttons", "buttons": [{"text": "Apply", "url": "javascript:alert(1)"}]}],
    [{"type": "buttons", "buttons": [{"text": "Apply", "url": "https://example.org", "copy_text": {"text": "x"}}]}],
    [{"type": "paragraph", "text": {"type": "date_time", "text": "tomorrow"}}],
])
def test_schema_rejects_wrong_names_and_invalid_actions(bad):
    assert validate_blocks(bad)


def test_schema_counts_nested_list_items():
    blocks = [{"type": "list", "items": [{"blocks": [{"type": "paragraph", "text": "x"}]}] * 250}]
    assert rich_usage(blocks)[0] == 501
    assert validate_blocks(blocks)


def test_schema_rejects_oversized_text():
    assert validate_blocks([{"type": "paragraph", "text": "x" * 32769}])


def test_legacy_fallback_keeps_expandable_details_and_original_link():
    blocks, _ = build_post("New", [card(benefits=["Funding"])])
    legacy = telegram_bot.legacy_rich_blocks(blocks)
    assert validate_blocks(legacy) == []
    assert "date_time" not in str(legacy) and "'buttons'" not in str(legacy)
    assert any(b["type"] == "details" for b in legacy)
    assert item()["url"] in str(legacy)


def test_timeout_does_not_retry_or_send_duplicate_html(monkeypatch):
    calls = []
    monkeypatch.setattr(telegram_bot, "BOT_TOKEN", "test")
    monkeypatch.setattr(telegram_bot, "CHANNEL_ID", "test-channel")
    monkeypatch.setattr(telegram_bot, "_rich_supported", True)
    def timeout(*args, **kwargs):
        calls.append(kwargs)
        raise requests.Timeout()
    monkeypatch.setattr(telegram_bot.requests, "post", timeout)
    blocks, html = build_post("New", [card()])
    with pytest.raises(telegram_bot.DeliveryUncertain):
        telegram_bot.publish(blocks, html)
    assert len(calls) == 1


def test_modern_rejection_can_downgrade_to_legacy_rich(monkeypatch):
    calls = []
    monkeypatch.setattr(telegram_bot, "BOT_TOKEN", "test")
    monkeypatch.setattr(telegram_bot, "CHANNEL_ID", "test")
    monkeypatch.setattr(telegram_bot, "_rich_supported", True)
    def post(payload, method):
        calls.append(payload)
        return (False, "Bad Request: unsupported block type") if len(calls) == 1 else (True, "")
    monkeypatch.setattr(telegram_bot, "_post", post)
    blocks, html = build_post("New", [card()])
    assert telegram_bot.publish(blocks, html)
    assert len(calls) == 2 and "buttons" not in str(calls[-1])


def test_html_fallback_obeys_send_message_limit():
    chunks = telegram_bot.split_message("<b>Grant</b>\n" + "x" * 10000)
    assert len(chunks) >= 3
    assert all(telegram_bot.utf16_len(c) <= 4096 for c in chunks)


def test_utf16_hard_split_does_not_overflow_on_emoji():
    chunks = telegram_bot.split_message("<b>" + "🎓" * 5000 + "</b>")
    assert all(telegram_bot.utf16_len(c) <= 4096 for c in chunks)
    assert all(not telegram_bot._open_tag_stack(c) for c in chunks)


def test_escaped_entities_are_not_broken_in_splitting():
    chunks = telegram_bot.split_message("<b>" + "&amp;" * 1800 + "</b>", limit=120)
    import re
    bodies = [re.sub(r"</?b>", "", c) for c in chunks]
    assert all(not re.sub(r"&amp;", "", c) for c in bodies)
    assert sum(c.count("&amp;") for c in bodies) == 1800


def test_rich_split_uses_nested_counts_and_card_boundaries():
    cards = [card(name=f"Fellowship {i}", url=f"https://example.org/apply/{i}", benefits=["Funding"] * 5) for i in range(20)]
    blocks, _ = build_post("New", cards)
    groups = telegram_bot._split_blocks(blocks, limit=90)
    assert len(groups) > 1
    assert all(rich_usage(g)[0] <= 90 for g in groups)
    assert all(not validate_blocks(g) for g in groups)


def test_multi_grant_digest_has_compact_clickable_navigation():
    cards = [card(name=f"Fellowship {i}", url=f"https://example.org/apply/{i}") for i in range(3)]
    blocks, _ = build_post("New", cards)
    assert not any(b["type"] == "details" and "ro'yxati" in b["summary"] for b in blocks)
    table = next(b for b in blocks if b["type"] == "table")
    assert table["caption"].startswith("Dasturlar ro'yxati")
    assert table["is_compact"] is True and len(table["cells"]) == 4
    targets = {row[0]["text"]["anchor_name"] for row in table["cells"][1:]}
    anchors = {b["name"] for b in blocks if b["type"] == "anchor"}
    assert targets == anchors
    assert validate_blocks(blocks) == []


def test_navigation_does_not_link_across_split_messages():
    cards = [card(name=f"Fellowship {i}", url=f"https://example.org/apply/{i}", benefits=["Funding"] * 5) for i in range(20)]
    blocks, _ = build_post("New", cards)
    groups = telegram_bot._split_blocks(blocks, limit=90)
    assert len(groups) > 1 and all(not validate_blocks(g) for g in groups)
    assert all("anchor_link" not in str(g) for g in groups)


def test_missing_navigation_target_is_rejected():
    assert validate_blocks([{"type": "paragraph", "text": {"type": "anchor_link", "text": "Jump", "anchor_name": "missing"}}])


def test_table_column_limit_is_enforced():
    cell = {"text": "x", "align": "left", "valign": "middle"}
    assert validate_blocks([{"type": "table", "cells": [[cell] * 21]}])


def test_pipeline_publishes_one_representative_and_records_source_alias(monkeypatch):
    first, second = item(1, summary="Funded research."), item(2)
    monkeypatch.setattr(main, "DB_READY", False)
    unique = main.deduplicate([first, second])
    monkeypatch.setattr(main, "DRY_RUN", False)
    configure_ai(monkeypatch, [card()])
    monkeypatch.setattr(telegram_bot, "BOT_TOKEN", "test")
    monkeypatch.setattr(telegram_bot, "CHANNEL_ID", "test")
    monkeypatch.setattr(telegram_bot, "_rich_supported", True)
    deliveries, saved = [], []
    def post(payload, method):
        assert method == "sendRichMessage"
        assert not validate_blocks(payload["rich_message"]["blocks"])
        deliveries.append(payload)
        return True, ""
    monkeypatch.setattr(telegram_bot, "_post", post)
    monkeypatch.setattr(main, "save_grants_batch", saved.extend)
    assert main.publish(unique) == 1
    assert len(deliveries) == 1
    assert [row["status"] for row in saved] == ["posted", "duplicate"]
    assert saved[1]["key"] == first["source_key"]


def test_ai_headline_cannot_label_partial_awards_fully_funded(monkeypatch):
    g = item()
    content = {"headline": "Barchasi to'liq moliyalashtirilgan!", "cards": [{**card(), "_source": g}]}
    monkeypatch.setattr(main, "generate_post_content", lambda batch: content)
    captured = []
    monkeypatch.setattr(main, "publish_post", lambda blocks, html: captured.append((blocks, html)) or True)
    monkeypatch.setattr(main, "save_grants_batch", lambda *args: None)
    assert main.publish([g]) == 1
    headline = next(b for b in captured[0][0] if b["type"] == "heading" and b["size"] == 2)
    assert headline["text"] == "1 ta yangi xalqaro imkoniyat"
    assert "Barchasi to'liq" not in captured[0][1]


def test_publish_preserves_native_forward_without_a_link_share_button(monkeypatch):
    monkeypatch.setattr(telegram_bot, "BOT_TOKEN", "test")
    monkeypatch.setattr(telegram_bot, "CHANNEL_ID", "@Nova_Grants")
    monkeypatch.setattr(telegram_bot, "_rich_supported", True)
    calls = []
    def post(payload, method="sendMessage"):
        calls.append((method, payload))
        return True, ""
    monkeypatch.setattr(telegram_bot, "_post", post)
    blocks, html = build_post("New", [card()])
    assert telegram_bot.publish_single(blocks, html)
    assert len(calls) == 1 and calls[0][0] == "sendRichMessage"
    assert "protect_content" not in calls[0][1]
    assert "share/url" not in str(calls)
