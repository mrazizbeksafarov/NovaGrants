"""Keep eligibility and deadline evidence when compressing long announcements."""

import re

from bs4 import BeautifulSoup

ELIGIBILITY_CONTEXT = re.compile(
    r"eligib|nationalit|citizen|countries|country|worldwide|international applicants"
    r"|residen|who can apply|who can participate|open to|uzbek|o.zbekiston|fuqaro",
    re.I,
)
DEADLINE_CONTEXT = re.compile(r"deadline|closing date|apply by|oxirgi muddat", re.I)
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

    sections = [text[:500]]
    eligibility = context(ELIGIBILITY_HEADING, 850) or context(ELIGIBILITY_CONTEXT, 850)
    deadline = context(DEADLINE_CONTEXT, 300)
    if eligibility:
        sections.append("Eligibility evidence:\n" + eligibility)
    if deadline:
        sections.append("Deadline evidence:\n" + deadline)
    return "\n\n".join(sections)[:limit]
