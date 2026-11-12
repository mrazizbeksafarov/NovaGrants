"""Read the official programme page before asking the editor to approve it."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from editorial_checks import foreign_enrollment_required
from link_resolver import _get, host_of, root_domain, is_aggregator, is_blocked
from opportunity_content import opportunity_summary, ELIGIBILITY_CONTEXT

MAX_PAGES = 32
WORKERS = 6
CHALLENGE = re.compile(r"verify (?:that )?you are human|just a moment|enable javascript and cookies|access denied", re.I)


@dataclass
class Evidence:
    grant: dict
    status: str
    reason: str = ""


def _document(response):
    if response is None or response.status_code != 200:
        return None
    if len(response.content) > 3_000_000:
        return None
    soup = BeautifulSoup(response.text, "html.parser")
    for node in soup.select("script, style, nav, footer, header, aside"):
        node.decompose()
    root = soup.select_one("main, article, [role=main]") or soup.body or soup
    text = root.get_text("\n", strip=True)
    if len(text) < 160 or CHALLENGE.search(text[:1500]):
        return None
    return root, text


def _programme_link(root, url, title):
    """At most one same-organisation hop from a generic homepage to its call."""
    if url.rstrip("/").count("/") > 2:
        return None
    words = set(re.findall(r"[a-z]{3,}|20\d{2}", title.lower())) - {
        "the", "for", "and", "with", "fully", "funded", "scholarships", "scholarship", "program", "programme"}
    years = {w for w in words if w.isdigit()}
    choices = []
    for a in root.select("a[href]"):
        label = a.get_text(" ", strip=True).lower()
        target = urljoin(url, a["href"])
        if root_domain(host_of(target)) != root_domain(host_of(url)) or is_blocked(target):
            continue
        tokens = set(re.findall(r"[a-z]{3,}|20\d{2}", label))
        if len(words & tokens) >= 3 and (not years or years & tokens):
            choices.append((len(words & tokens), target))
    return max(choices)[1] if choices else None


def verify_one(grant):
    url = grant.get("url", "")
    try:
        if not url or is_aggregator(url) or is_blocked(url):
            return Evidence(grant, "retry", "rasmiy havola tekshirilmagan")
        response = _get(url)
        document = _document(response)
        if document is None:
            return Evidence(grant, "retry", "rasmiy sahifa o'qilmadi")
        final_url = getattr(response, "url", None) or url
        if is_aggregator(final_url) or is_blocked(final_url):
            return Evidence(grant, "retry", "rasmiy bo'lmagan sahifaga yo'naltirildi")
        root, text = document
        deeper = _programme_link(root, final_url, grant.get("title", ""))
        if deeper:
            next_response = _get(deeper)
            next_document = _document(next_response)
            next_url = getattr(next_response, "url", None) or deeper
            if (next_document is None or is_aggregator(next_url) or is_blocked(next_url)
                    or root_domain(host_of(next_url)) != root_domain(host_of(final_url))):
                return Evidence(grant, "retry", "dastur e'loni o'qilmadi")
            root, text = next_document
            final_url = next_url
        if not ELIGIBILITY_CONTEXT.search(text):
            return Evidence(grant, "retry", "rasmiy sahifada qatnashish dalili yetarli emas")
        if foreign_enrollment_required(text):
            return Evidence(grant, "ineligible", "xorijda avvaldan o'qish sharti bor")
        verified = dict(grant)
        verified["summary"] = opportunity_summary(str(root), limit=6000)
        verified["official_evidence_url"] = final_url
        return Evidence(verified, "ready")
    except Exception as exc:
        # One broken page must not abort the other programmes. Never mark it
        # skipped: missing evidence is retryable, not proven ineligibility.
        return Evidence(grant, "retry", f"rasmiy sahifa xatosi: {type(exc).__name__}")


def verify_all(grants):
    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        return list(executor.map(verify_one, grants[:MAX_PAGES]))
