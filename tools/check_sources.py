"""Check production feeds/channels and freshness without AI/DB/Telegram writes."""
import argparse
import concurrent.futures
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import feedparser
from bs4 import BeautifulSoup
import http_client
from link_resolver import clean_url, host_of
from scraper import MAX_AGE_DAYS, _entry_age_days, _post_age_days
from sources import SOURCES


def inspect_feed(content, src):
    feed = feedparser.parse(content)
    entries = [e for e in feed.entries if clean_url(e.get('link', '')) and e.get('title')]
    max_age = src.get('max_age_days', MAX_AGE_DAYS)
    ages = [_entry_age_days(e) for e in entries]
    fresh = [e for e, age in zip(entries, ages) if max_age is None or age is None or age <= max_age]
    return {
        'status': 'OK' if fresh else 'STALE' if entries else 'EMPTY_OR_NOT_FEED',
        'entries': len(entries), 'fresh_entries': len(fresh),
        'unknown_dates': sum(age is None for age in ages),
        'newest_age_days': min((age for age in ages if age is not None), default=None),
        'date_policy': 'live_details' if max_age is None else f'max_{max_age}_days',
        'samples': [{'title': e.get('title', ''), 'url': e.get('link', '')} for e in fresh[:2]],
    }


def check_rss(src):
    response = http_client.get(src['url'], timeout=15)
    if response is None:
        return {'status': 'CONNECTION_FAILED'}
    if response.status_code != 200:
        return {'status': f'HTTP_{response.status_code}'}
    return inspect_feed(response.content, src)


def check_telegram(src):
    response = http_client.get(f"https://t.me/s/{src['channel']}", timeout=15)
    if response is None:
        return {'status': 'CONNECTION_FAILED'}
    if response.status_code != 200:
        return {'status': f'HTTP_{response.status_code}'}
    soup = BeautifulSoup(response.text, 'html.parser')
    wrappers = [w for w in soup.select('.tgme_widget_message') if w.select_one('.tgme_widget_message_text')]
    fresh = [w for w in wrappers if (_post_age_days(w) or 0) <= MAX_AGE_DAYS]
    links = [a['href'] for w in fresh for a in w.select('.tgme_widget_message_text a[href^="http"]')
             if host_of(a['href']) not in {'t.me', 'telegram.me'}]
    return {'status': 'OK' if fresh else 'STALE' if wrappers else 'NO_PREVIEW',
            'entries': len(wrappers), 'fresh_entries': len(fresh), 'external_links': len(links)}


def check_grantsgov(src):
    response = http_client.session.post(src['url'], timeout=15,
                                       json={'rows': 5, 'keyword': '', 'oppStatuses': 'posted'})
    if response is None:
        return {'status': 'CONNECTION_FAILED'}
    if response.status_code != 200:
        return {'status': f'HTTP_{response.status_code}'}
    hits = response.json().get('data', {}).get('oppHits', [])
    return {'status': 'OK' if hits else 'EMPTY', 'entries': len(hits)}


def check(src):
    base = {'id': src['id'], 'type': src['type'], 'kind': src['kind'],
            'enabled': src.get('enabled', True),
            'url': src.get('url') or f"https://t.me/s/{src.get('channel', '')}"}
    handler = {'rss': check_rss, 'telegram': check_telegram, 'grantsgov': check_grantsgov}.get(src['type'])
    try:
        return {**base, **(handler(src) if handler else {'status': 'UNSUPPORTED_TYPE'})}
    except Exception as exc:
        return {**base, 'status': type(exc).__name__}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--all', action='store_true', help='Include deliberately disabled sources')
    parser.add_argument('--source', action='append', help='Only these source IDs (repeatable)')
    parser.add_argument('--json', type=Path, help='Save a timestamped machine-readable report')
    args = parser.parse_args()
    if args.source:
        unknown = set(args.source) - {s['id'] for s in SOURCES}
        if unknown:
            parser.error(f"Unknown source IDs: {', '.join(sorted(unknown))}")
    selected = [s for s in SOURCES if (args.all or s.get('enabled', True))
                and (not args.source or s['id'] in args.source)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(check, selected))
    for row in results:
        print(f"{row['id']:<26} {row['status']:<22} "
              f"fresh={row.get('fresh_entries', '-')} total={row.get('entries', '-')}", flush=True)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps({'checked_at': datetime.now(timezone.utc).isoformat(),
                                        'sources': results}, ensure_ascii=False, indent=2), encoding='utf-8')
    ok = sum(row['status'] == 'OK' for row in results)
    print(f'\nWorking with fresh entries: {ok}/{len(results)}')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
