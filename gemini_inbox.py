"""Read opportunities that the owner's Gemini task files as GitHub issues.

A scheduled Gemini task (Google AI Pro, GitHub MCP) opens one issue a day,
titled "Nova inbox YYYY-MM-DD" with the label ``nova-inbox``, containing
blocks between ``NOVA-GRANT`` and ``END``. The repository is public, so only
issues opened by an allowed author are read; everything in them is data and
goes through the same official-link and Uzbekistan checks as any source.
"""

import os
import re
from datetime import datetime, timezone

import requests

from link_resolver import (canonical_url_key, clean_url, is_aggregator, is_blocked,
                           program_fingerprint, title_fingerprint, url_key)
from rich_schema import valid_web_url

LABEL = "nova-inbox"
SOURCE_ID = "gemini-inbox"
PENDING = {"retry", "defer", "ready"}
MAX_OPEN_DAYS = 3
API = "https://api.github.com"
MAX_ITEMS = 30  # inbox items are checked first and must fit the 32-page budget
FIELDS = {"nomi": "name", "havola": "url", "muddat": "deadline", "turi": "type",
          "kimlar": "who", "dalil": "evidence", "qisqacha": "summary"}
BLOCK = re.compile(r"NOVA-GRANT\s*(.*?)\s*\bEND\b", re.S | re.I)
LINE = re.compile(r"^[\s>*_`-]*([A-Za-z']+)[*_`]*\s*:[*_`]*\s*(.*)$")
MARKDOWN_LINK = re.compile(r"\[[^\]]*\]\((https?://[^)\s]+)\)")


def _repo():
    return os.getenv("NOVA_INBOX_REPO") or os.getenv("GITHUB_REPOSITORY", "")


def _authors():
    configured = os.getenv("NOVA_INBOX_AUTHORS") or os.getenv("GITHUB_REPOSITORY_OWNER", "")
    return {name.strip().lower() for name in configured.split(",") if name.strip()}


def _headers():
    token = os.getenv("GITHUB_TOKEN", "")
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def configured():
    return bool(_repo() and _authors() and os.getenv("GITHUB_TOKEN"))


def _clean_value(value):
    value = MARKDOWN_LINK.sub(r"\1", value.strip())
    value = value.strip().strip("*_`").strip()
    if value.startswith("<") and value.endswith(">"):
        value = value[1:-1]
    return value.strip().strip('"“”').strip()


def parse(body):
    """Return the well-formed NOVA-GRANT blocks of an issue body."""
    items = []
    for block in BLOCK.findall(body or ""):
        fields = {}
        for raw in block.splitlines():
            match = LINE.match(raw)
            if match and match[1].lower() in FIELDS:
                fields[FIELDS[match[1].lower()]] = _clean_value(match[2])
        url = clean_url(fields.get("url", "")) or fields.get("url", "")
        if fields.get("name") and valid_web_url(url):
            fields["url"] = url
            items.append(fields)
    return items


def to_candidate(fields, issue_url):
    """A resolved candidate: the official link is the issue's Havola."""
    title, url = fields["name"][:250], fields["url"]
    deadline = fields.get("deadline", "")
    lines = [f"Kimlar: {fields['who']}" if fields.get("who") else "",
             f"Official statement: \"{fields['evidence']}\"" if fields.get("evidence") else "",
             fields.get("summary", ""),
             f"Deadline: {deadline}" if re.match(r"\d{4}-\d{2}-\d{2}$", deadline) else ""]
    return {"title": title, "url": url, "url_key": url_key(url),
            "canonical_url_key": canonical_url_key(url, title),
            "program_fingerprint": program_fingerprint(title, url),
            "fingerprint": title_fingerprint(title),
            "source_url": issue_url, "source_key": "gemini-inbox:" + url_key(url),
            "source_id": SOURCE_ID, "kind": "official", "topic": fields.get("type", ""),
            "summary": "\n".join(line for line in lines if line)}


def fetch():
    """(candidates, issues, problems). Never raises: the inbox is optional."""
    if not configured():
        return [], [], []
    try:
        response = requests.get(f"{API}/repos/{_repo()}/issues", headers=_headers(), timeout=30,
                                params={"labels": LABEL, "state": "open", "per_page": 20})
        response.raise_for_status()
        issues = response.json()
    except (requests.RequestException, ValueError) as exc:
        return [], [], [f"Gemini inbox o'qilmadi ({type(exc).__name__})"]
    authors, candidates, accepted, problems, seen = _authors(), [], [], [], set()
    for issue in issues if isinstance(issues, list) else []:
        if issue.get("pull_request"):
            continue
        author = str((issue.get("user") or {}).get("login", "")).lower()
        if author not in authors:
            problems.append(f"Gemini inbox: #{issue.get('number')} begona muallifdan, e'tiborsiz qoldirildi")
            continue
        accepted.append(issue)
        for fields in parse(issue.get("body")):
            url = fields["url"]
            if is_aggregator(url) or is_blocked(url) or url in seen:
                continue
            seen.add(url)
            candidates.append(to_candidate(fields, issue.get("html_url", "")))
    return candidates[:MAX_ITEMS], accepted, problems


def _close(number, report):
    try:
        requests.post(f"{API}/repos/{_repo()}/issues/{number}/comments", headers=_headers(),
                      json={"body": report}, timeout=30).raise_for_status()
        requests.patch(f"{API}/repos/{_repo()}/issues/{number}", headers=_headers(),
                       json={"state": "closed", "state_reason": "completed"}, timeout=30).raise_for_status()
    except requests.RequestException as exc:
        print(f"   Gemini inbox #{number} yopilmadi ({type(exc).__name__}); keyingi yurishda qayta o'qiladi.")


def _age_days(issue):
    try:
        created = datetime.fromisoformat(str(issue.get("created_at", "")).replace("Z", "+00:00"))
    except ValueError:
        return MAX_OPEN_DAYS
    return (datetime.now(timezone.utc) - created).days


def finish(issues, candidates, decisions):
    """Close an issue once none of its items is still pending.

    Items left for a later run (unverified, or beyond today's single digest)
    keep the issue open so the next run reads them again; already posted
    ones are then dropped as duplicates. After MAX_OPEN_DAYS it closes anyway.
    """
    last = {}
    for decision in decisions:
        last[decision["url"]] = decision
    for issue in issues:
        own = [g for g in candidates if g["source_url"] == issue.get("html_url")]
        pending = [g for g in own if (last.get(g["url"]) or {}).get("state") in PENDING]
        if pending and _age_days(issue) < MAX_OPEN_DAYS:
            print(f"   Gemini inbox #{issue.get('number')}: {len(pending)} ta imkoniyat keyingi yurishga qoldi, issue ochiq turadi.")
            continue
        _close(issue.get("number"), outcome_report(own, decisions))


def outcome_report(candidates, decisions):
    """One line per inbox item from the selection audit trail."""
    labels = {"publish": "✅ tanlandi", "posted": "✅ kanalga chiqdi", "prepared": "✅ tayyorlandi",
              "reject": "❌ rad etildi", "review": "⏸ tekshiruvga qoldi", "retry": "↻ keyingi yurishda",
              "defer": "↻ keyingi postga qoldi", "duplicate": "= takror"}
    last = {}
    for decision in decisions:
        last[decision["url"]] = decision
    lines = ["Nova Grants bot natijasi:", ""]
    for grant in candidates:
        decision = last.get(grant["url"])
        state = labels.get(decision["state"], decision["state"]) if decision else "= avval chiqqan (takror)"
        reason = f" ({decision['reason']})" if decision and decision.get("reason") else ""
        lines.append(f"- {grant['title'][:90]} — {state}{reason}")
    return "\n".join(lines)
