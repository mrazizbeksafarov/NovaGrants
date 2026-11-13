"""Read the official programme page before asking the editor to approve it."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from editorial_checks import foreign_enrollment_required
from link_resolver import _get, host_of, root_domain, is_aggregator, is_blocked
from opportunity_content import opportunity_summary, readable_text, ELIGIBILITY_CONTEXT, GEOGRAPHIC_CONTEXT
from selection_policy import established_issuer, stated_application_fee, EVENT

MAX_PAGES = 32
WORKERS = 6
MAX_ELIGIBILITY_PAGES = 2
ELIGIBILITY_LINK = re.compile(
    r"eligib|who can apply|who may apply|country list|list of countries|participating countries"
    r"|nationalit|citizenship|criteria|requirements|qualifications", re.I)
DOCUMENT_FILE = re.compile(r"\.(?:pdf|docx?|xlsx?|pptx?|zip)(?:$|[?#])", re.I)
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
    for node in soup.select("script, style, nav, footer, aside"):
        node.decompose()
    root = soup.select_one("main, article, [role=main]") or soup.body or soup
    text = readable_text(root)
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


def _eligibility_links(root, url):
    """Same-site pages that state who may apply (country lists, criteria).

    Many official calls keep nationality rules on a separate "Eligibility" or
    "Country list" page. Without it the editor can only answer
    insufficient_evidence and a genuinely open call is retried every day.
    """
    here = url.split("#")[0].rstrip("/")
    seen, links = set(), []
    for a in root.select("a[href]"):
        label = a.get_text(" ", strip=True)
        target = urljoin(url, a["href"]).split("#")[0]
        if (not target.startswith("http") or target.rstrip("/") == here or target in seen
                or DOCUMENT_FILE.search(target) or is_aggregator(target) or is_blocked(target)
                or root_domain(host_of(target)) != root_domain(host_of(url))):
            continue
        by_label = bool(ELIGIBILITY_LINK.search(label))
        if by_label or ELIGIBILITY_LINK.search(target.rsplit("/", 1)[-1] or target):
            seen.add(target)
            links.append((not by_label, len(links), target))
    return [target for *_, target in sorted(links)[:MAX_ELIGIBILITY_PAGES]]


def _with_eligibility_pages(root, text, url):
    """Append official eligibility subpages when the call page lacks a country scope."""
    if GEOGRAPHIC_CONTEXT.search(text):
        return str(root), text, []
    html, texts, used = [str(root)], [text], []
    for link in _eligibility_links(root, url):
        response = _get(link)
        document = _document(response)
        final = getattr(response, "url", None) or link
        if (document is None or is_aggregator(final) or is_blocked(final)
                or root_domain(host_of(final)) != root_domain(host_of(url))):
            continue
        sub_root, sub_text = document
        html.append(str(sub_root))
        texts.append(sub_text)
        used.append(final)
    return "\n".join(html), "\n".join(texts), used


LOCAL_LANGUAGE = re.compile(
    r"\b(?:uchun|bo.yicha|ariza|tanlov|yoshlar|talabalar|o.zbekiston|respublika|qabul qilinadi"
    r"|учун|бўйича|ўзбекистон|ёшлар|танлов|узбекистан|республик)\b", re.I)
MIN_LISTING = 120


def _local_call(url, text):
    """An Uzbek-language call on an Uzbek site is, by itself, open to Uzbekistan."""
    return host_of(url).endswith(".uz") or len(LOCAL_LANGUAGE.findall(text or "")) >= 3


def _listing_evidence(grant, reason, official_text=""):
    """The official link stays; the announcement text supplies who may apply.

    Many official sites block bots or keep eligibility out of the call page.
    The channel's two conditions are an official link and Uzbekistan
    eligibility, so the announcement's own wording may prove eligibility;
    assess() still requires an explicit Uzbekistan/worldwide scope in it.
    """
    listing = str(grant.get("summary") or "").strip()
    if len(listing) < MIN_LISTING:
        return Evidence(grant, "retry", reason)
    if foreign_enrollment_required(listing):
        return Evidence(grant, "ineligible", "xorijda avvaldan o'qish sharti bor")
    verified = dict(grant)
    parts = [official_text, "E'lon matni:\n" + listing[:2500]] if official_text else [listing[:4000]]
    verified["summary"] = "\n\n".join(parts)
    verified["evidence_from_listing"] = True
    return Evidence(verified, "ready")


def verify_one(grant):
    url = grant.get("url", "")
    try:
        if not url or is_aggregator(url) or is_blocked(url):
            return Evidence(grant, "retry", "rasmiy havola tekshirilmagan")
        response = _get(url)
        document = _document(response)
        if document is None:
            return _listing_evidence(grant, "rasmiy sahifa o'qilmadi")
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
        html, text, extra_pages = _with_eligibility_pages(root, text, final_url)
        if not ELIGIBILITY_CONTEXT.search(text) and not _local_call(final_url, text):
            return _listing_evidence(grant, "rasmiy sahifada qatnashish dalili yetarli emas",
                                     opportunity_summary(html, limit=3500))
        if (EVENT.search(grant.get("title", ""))
                and stated_application_fee(text) and not established_issuer(final_url)):
            return Evidence(grant, "review", "paid_private_forum")
        if foreign_enrollment_required(text):
            return Evidence(grant, "ineligible", "xorijda avvaldan o'qish sharti bor")
        verified = dict(grant)
        verified["summary"] = opportunity_summary(html, limit=6000)
        verified["official_evidence_url"] = final_url
        if extra_pages:
            verified["official_evidence_pages"] = extra_pages
        return Evidence(verified, "ready")
    except Exception as exc:
        # One broken page must not abort the other programmes. Never mark it
        # skipped: missing evidence is retryable, not proven ineligibility.
        return Evidence(grant, "retry", f"rasmiy sahifa xatosi: {type(exc).__name__}")


def verify_all(grants):
    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        return list(executor.map(verify_one, grants[:MAX_PAGES]))
