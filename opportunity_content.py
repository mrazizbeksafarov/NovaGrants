"""Keep eligibility and deadline evidence when compressing long announcements."""

import re

from bs4 import BeautifulSoup

ELIGIBILITY_CONTEXT = re.compile(
    r"eligib|nationalit|citizen|countries|country|worldwide|international applicants"
    r"|residen|who can apply|who can participate|open to|uzbek|o.zbekiston|fuqaro",
    # Russian eligibility must not disappear from otherwise valid official calls.
    re.I,
)
ELIGIBILITY_CONTEXT = re.compile(ELIGIBILITY_CONTEXT.pattern + r"|граждан|заявител|участник|всех стран|узбекистан|ўзбекистон", re.I)
DEADLINE_CONTEXT = re.compile(r"deadline|closing date|apply by|application[s]?\s+close|on or before|oxirgi muddat", re.I)
FUNDING_CONTEXT = re.compile(r"costs? covered|financial support|funding (?:details|coverage)|scholarship (?:covers|benefits)|benefits|stipend|tuition waiver|fully.funded", re.I)
GEOGRAPHIC_CONTEXT = re.compile(r"uzbekistan|o.zbekiston|all nationalities|all countries|worldwide|geographic eligibility|no geographic restrictions|узбекистан|ўзбекистон|всех стран|любой страны", re.I)
RESTRICTION_CONTEXT = re.compile(
    r"not eligible|ineligible|must (?:be|have|hold|reside)|only (?:citizens|residents)"
    r"|enroll|matriculat|permanent residen|\bCPT\b|\bOPT\b|outside the"
    r"|application (?:fee|processing)|non.refundable|deposit|costs? not covered", re.I)
ELIGIBILITY_HEADING = re.compile(
    r"eligibility|eligible (?:countries|nationalities|applicants)|who can apply"
    r"|citizenship|fuqarolik|kimlar (?:qatnash|ishtirok)", re.I,
)


BLOCK_TAGS = ["address", "article", "aside", "blockquote", "dd", "details", "div", "dl", "dt",
              "fieldset", "figcaption", "figure", "footer", "form", "h1", "h2", "h3", "h4", "h5",
              "h6", "header", "hr", "li", "main", "nav", "ol", "p", "pre", "section", "summary",
              "table", "tbody", "td", "th", "thead", "tr", "ul", "option"]


def readable_text(node) -> str:
    """Text as a browser shows it: line breaks only between blocks.

    Office/SharePoint pages split single words across inline spans
    ("repres<span>ent</span>ation"). Joining every text node with a newline
    turned those words into "repres\\nent\\nation", so a correct verbatim
    model quote could never match the evidence and good calls were retried
    forever. Inline elements are now joined exactly as rendered.
    """
    for br in node.find_all("br"):
        br.replace_with("\n")
    for block in node.find_all(BLOCK_TAGS):
        block.insert_before("\n")
        block.insert_after("\n")
    lines = (re.sub(r"[ \t\r\f\v   ]+", " ", line).strip()
             for line in node.get_text("").splitlines())
    return "\n".join(line for line in lines if line)


def opportunity_summary(raw: str, limit: int = 1800) -> str:
    """Retain an introduction plus evidence; do not discard late eligibility lists."""
    soup = BeautifulSoup(raw or "", "html.parser")
    for node in soup.select("script, style, nav, footer, aside"):
        node.decompose()
    text = readable_text(soup)
    if len(text) <= limit:
        return text

    def context(pattern, size):
        match = pattern.search(text)
        return text[max(0, match.start() - 40):match.start() + size] if match else ""

    # Preserve late exclusions and applicant costs as well as the first positive
    # eligibility claim. A first "all nationalities" line is not the whole rule.
    sections = []
    # A detailed age/motivation section can otherwise consume the entire first
    # eligibility window before the actual country list is reached.
    geography = []
    for match in GEOGRAPHIC_CONTEXT.finditer(text):
        excerpt = text[max(0, match.start()-100):match.start()+350]
        if not any(excerpt in existing for existing in geography):
            geography.append(excerpt)
        if len(geography) == 4:
            break
    if geography:
        sections.append("Geographic eligibility:\n" + "\n".join(geography))
    sections.append(text[:500])
    eligibility = context(ELIGIBILITY_HEADING, 850) or context(ELIGIBILITY_CONTEXT, 850)
    funding = context(FUNDING_CONTEXT, 950)
    deadline = context(DEADLINE_CONTEXT, 300)
    if eligibility:
        sections.append("Eligibility evidence:\n" + eligibility)
    if funding:
        sections.append("Funding evidence:\n" + funding)
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
    if limit >= 4000:
        # Reserve space for every decision dimension instead of letting long,
        # repeated exclusions push geography/funding/deadline out of the input.
        fields = [
            ("Restrictions and costs", "\n".join(snippets), 1700),
            ("Geographic eligibility", "\n".join(geography), 900),
            ("Application deadline", deadline, 500),
            ("Financial support", funding, 950),
            ("Applicant requirements", eligibility, 1000),
            ("Programme introduction", text[:400], 400),
        ]
        return "\n\n".join(f"{label}:\n{value[:budget]}" for label, value, budget in fields if value)[:limit]
    return "\n\n".join(sections)[:limit]
