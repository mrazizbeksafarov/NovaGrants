"""Keep eligibility and deadline evidence when compressing long announcements."""

import re

from bs4 import BeautifulSoup

ELIGIBILITY_CONTEXT = re.compile(
    r"eligib|nationalit|citizen|countries|country|worldwide|international applicants"
    r"|residen|who can apply|who can participate|open to|uzbek|o.zbekiston|fuqaro",
    re.I,
)
DEADLINE_CONTEXT = re.compile(r"deadline|closing date|apply by|oxirgi muddat", re.I)
RESTRICTION_CONTEXT = re.compile(
    r"not eligible|ineligible|must (?:be|have|hold|reside)|only (?:citizens|residents)"
    r"|enroll|matriculat|permanent residen|\bCPT\b|\bOPT\b|outside the"
    r"|application (?:fee|processing)|non.refundable|deposit|costs? not covered", re.I)
ELIGIBILITY_HEADING = re.compile(
    r"eligibility|eligible (?:countries|nationalities|applicants)|who can apply"
    r"|citizenship|fuqarolik|kimlar (?:qatnash|ishtirok)", re.I,
)


def opportunity_summary(raw: str, limit: int = 1800) -> str:
    """Retain an introduction plus evidence; do not discard late eligibility lists."""
    soup = BeautifulSoup(raw or "", "html.parser")
    for node in soup.select("script, style, nav, footer, aside"):
        node.decompose()
    text = re.sub(r"[ \t]+", " ", soup.get_text("\n", strip=True))
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) <= limit:
        return text

    def context(pattern, size):
        match = pattern.search(text)
        return text[max(0, match.start() - 40):match.start() + size] if match else ""

    # Preserve late exclusions and applicant costs as well as the first positive
    # eligibility claim. A first "all nationalities" line is not the whole rule.
    sections = [text[:500]]
    eligibility = context(ELIGIBILITY_HEADING, 850) or context(ELIGIBILITY_CONTEXT, 850)
    deadline = context(DEADLINE_CONTEXT, 300)
    if eligibility:
        sections.append("Eligibility evidence:\n" + eligibility)
    snippets = []
    for match in RESTRICTION_CONTEXT.finditer(text):
        start = text.rfind("\n", 0, match.start()) + 1
        start = max(start, match.start() - 100)
        end = text.find("\n", match.end())
        if end < 0:
            end = len(text)
        # A short heading such as "Costs Not Covered" needs its following
        # bullets; preserving the heading alone hides the actual costs.
        if end - start < 120:
            end = min(len(text), end + 450)
        excerpt = text[start:min(end, start + 700)]
        if excerpt and excerpt not in snippets and excerpt not in eligibility:
            snippets.append(excerpt)
    # The larger official-page budget prioritizes every observed exclusion
    # before promotional introduction and navigational material.
    if limit >= 4000 and snippets:
        sections.insert(0, "Restrictions and costs:\n" + "\n".join(snippets))
    if deadline:
        sections.append("Deadline evidence:\n" + deadline)
    return "\n\n".join(sections)[:limit]
