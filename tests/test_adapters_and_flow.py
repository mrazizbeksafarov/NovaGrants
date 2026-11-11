"""Exercise parser adapters and full orchestration using deterministic responses."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import feedparser
import pytest

import database
import http_client
import link_resolver
import main
import scraper
import telegram_bot
from test_reliability import FakeDatabase
from test_sources_and_rich import card, configure_ai, item


def rss_entry(title="Global Research Fellowship", link="https://example.org/fellowship", age=0):
    date = (datetime.now(timezone.utc) - timedelta(days=age)).timetuple()
    return {"title": title, "link": link, "published_parsed": date,
            "summary": "<p>All nationalities may apply.</p>"}


def test_rss_pagination_filters_stale_and_duplicate_entries(monkeypatch):
    calls = []
    def feed(url, source):
        calls.append(url)
        entries = [rss_entry(), rss_entry(age=90, link="https://example.org/old")]
        if len(calls) > 1:
            entries.append(rss_entry("Another Fellowship", "https://example.org/another"))
        return SimpleNamespace(entries=entries)
    monkeypatch.setattr(scraper, "_fetch_feed", feed)
    results = scraper.scrape_rss({"id": "global", "url": "https://example.org/feed?lang=en", "kind": "official", "pages": 2})
    assert len(results) == 2
    assert calls[1].endswith("&paged=2")
    assert all("All nationalities" in r["summary"] for r in results)


def test_full_rss_content_preserves_official_apply_link(monkeypatch):
    e = rss_entry()
    e["content"] = [{"value": '<p>All nationalities.</p><a href="https://university.example/apply">Apply now</a>'}]
    monkeypatch.setattr(scraper, "_fetch_feed", lambda *args: SimpleNamespace(entries=[e]))
    result = scraper.scrape_rss({"id": "global", "url": "https://example.org/feed/", "kind": "aggregator"})[0]
    assert "university.example/apply" in result["feed_html"]


def test_feed_long_retry_after_is_deferred_not_retried_early(monkeypatch):
    calls = []
    def get(*args, **kwargs):
        calls.append(args)
        return SimpleNamespace(status_code=429, headers={"Retry-After": "120"})
    monkeypatch.setattr(scraper._session, "get", get)
    assert scraper._fetch_feed("https://example.org/feed", "global") is None
    assert len(calls) == 1


def test_feed_short_retry_after_is_honoured(monkeypatch):
    replies = iter([SimpleNamespace(status_code=503, headers={"Retry-After": "2"}),
                    SimpleNamespace(status_code=200, content=b'<rss version="2.0"><channel><title>Feed</title></channel></rss>')])
    sleeps = []
    monkeypatch.setattr(scraper._session, "get", lambda *args, **kwargs: next(replies))
    monkeypatch.setattr(scraper.time, "sleep", sleeps.append)
    assert scraper._fetch_feed("https://example.org/feed", "global") is not None
    assert sleeps == [2]


def telegram_html(link, date=None):
    date = date or datetime.now(timezone.utc).isoformat()
    return f'''<div class="tgme_widget_message"><time datetime="{date}"></time>
    <a class="tgme_widget_message_date" href="https://t.me/grants/123">Date</a>
    <div class="tgme_widget_message_text">International Research Fellowship 2027
    All nationalities including Uzbekistan may apply for this fully funded research opportunity.
    <a href="{link}">Apply now</a></div></div>'''


def test_telegram_aggregator_link_is_kept_for_resolution(monkeypatch):
    article = "https://opportunitiespedia.com/research-fellowship/"
    monkeypatch.setattr(scraper._session, "get", lambda *args, **kwargs: SimpleNamespace(status_code=200, text=telegram_html(article)))
    result = scraper.scrape_telegram({"id": "tg:global", "channel": "grants", "kind": "aggregator"})
    assert len(result) == 1 and result[0]["direct_url"] == article
    assert "Uzbekistan" in result[0]["summary"]


def test_stale_telegram_posts_are_not_reintroduced(monkeypatch):
    old = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
    monkeypatch.setattr(scraper._session, "get", lambda *args, **kwargs: SimpleNamespace(status_code=200, text=telegram_html("https://example.org/apply", old)))
    assert scraper.scrape_telegram({"id": "tg:global", "channel": "grants", "kind": "aggregator"}) == []


def test_fetch_all_deduplicates_the_same_article_across_adapters(monkeypatch):
    monkeypatch.setattr(scraper, "enabled_sources", lambda: [{"id": "one"}, {"id": "two"}])
    monkeypatch.setattr(scraper, "_fetch_one", lambda src: [{"title": "Fellowship", "url": "https://example.org/grant?utm_source=" + src["id"]}])
    results = scraper.fetch_all()
    assert len(results) == 1 and results[0]["source_key"] == "example.org/grant"


def test_curl_429_does_not_switch_clients(monkeypatch):
    client = http_client.Client()
    response = SimpleNamespace(status_code=429)
    monkeypatch.setattr(client, "_curl_get", lambda *args, **kwargs: response)
    def forbidden(*args, **kwargs):
        raise AssertionError("Must respect 429")
    monkeypatch.setattr(client._plain, "get", forbidden)
    assert client.get("https://example.org") is response


def test_missing_curl_client_uses_plain_http(monkeypatch):
    client = http_client.Client()
    client._curl_session = None
    response = SimpleNamespace(status_code=200)
    monkeypatch.setattr(client._plain, "get", lambda *args, **kwargs: response)
    assert client.get("https://example.org") is response


def test_plain_failure_preserves_original_response(monkeypatch):
    client = http_client.Client()
    response = SimpleNamespace(status_code=403)
    monkeypatch.setattr(client, "_curl_get", lambda *args, **kwargs: response)
    def fail(*args, **kwargs):
        raise TimeoutError()
    monkeypatch.setattr(client._plain, "get", fail)
    assert client.get("https://example.org") is response


def test_resolver_long_retry_after_sets_shared_cooldown(monkeypatch):
    url = "https://rate-limited.example/apply"
    calls = []
    monkeypatch.setattr(link_resolver, "_throttle", lambda host: None)
    monkeypatch.setattr(link_resolver, "_host_blocked_until", {})
    def get(*args, **kwargs):
        calls.append(args)
        return SimpleNamespace(status_code=429, headers={"Retry-After": "120"})
    monkeypatch.setattr(link_resolver._session, "get", get)
    assert link_resolver._get(url).status_code == 429
    assert link_resolver._get(url) is None
    assert len(calls) == 1


def test_full_run_deduplicates_publishes_and_persists(monkeypatch, capsys):
    db = FakeDatabase()
    monkeypatch.setattr(database, "supabase", db)
    monkeypatch.setattr(database, "HAS_SEMANTIC_SLUG", True)
    monkeypatch.setattr(main, "DB_READY", False)
    monkeypatch.setattr(main, "DRY_RUN", False)
    monkeypatch.setattr(main, "init_db", lambda **kwargs: True)
    monkeypatch.setattr(main, "send_reminders", lambda: None)
    monkeypatch.setattr(main, "notify_admin", lambda *args: True)
    raw = []
    for n in (1, 2):
        g = item(n, url=f"https://opportunitiespedia.com/post/{n}")
        g["feed_html"] = f'<p>{g["summary"]}</p><a href="{item()["url"]}">Official website</a>'
        raw.append(g)
    monkeypatch.setattr(main, "fetch_all", lambda: raw)
    monkeypatch.setattr(link_resolver, "follow_redirects", lambda url: url)
    configure_ai(monkeypatch, [card()])
    monkeypatch.setattr(telegram_bot, "BOT_TOKEN", "test")
    monkeypatch.setattr(telegram_bot, "CHANNEL_ID", "channel")
    monkeypatch.setattr(telegram_bot, "_rich_supported", True)
    deliveries = []
    monkeypatch.setattr(telegram_bot, "_post", lambda payload, method: (deliveries.append(payload) or True, ""))
    main.run()
    assert len(deliveries) == 1
    assert sum(r["status"] == "posted" for r in db.rows) == 1
    assert sum(r["status"] == "duplicate" for r in db.rows) == 1
    assert "Yakunlandi: 1 ta" in capsys.readouterr().out
