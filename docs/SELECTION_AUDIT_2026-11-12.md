# Nova Grants selection audit

Audience: individuals applying while currently living/studying in Uzbekistan.
Objective: useful, open, accurately described opportunities, with official
eligibility evidence and one clear application route. This audit includes
discovery, resolution, persistence, editorial selection, ranking, reminders and
publication; source keywords are not an eligibility oracle.

## Confirmed failures and corrections

| Layer | Reproduced failure | Corrected decision |
|---|---|---|
| News | Winners report passed because it mentioned eligibility/deadline | Result headlines stay excluded |
| Applicant | An institution-only call passed because its text mentioned students | Explicit organization-only application is rejected; mixed routes are reviewed |
| False rejection | Individual PhD/postdoctoral call failed because it needed a host institution | Planned host/admission support is evaluated separately from legal applicant type |
| Location | Worldwide nationality overrode existing US student/resident requirement | Existing foreign residence/enrolment is checked independently |
| Country evidence | Generic international/developing-country language was treated as sufficient | Explicit country/group evidence or a supported local call is required |
| Long pages | Geography, funding or deadline was truncated by a long requirements section | Separate bounded evidence windows retain each decision dimension |
| Fees | Paid private forums were selected as fully funded opportunities | Held before editorial calls when detectable and again by independent policy |
| Reputation | Academic venue/name could look like the issuer | Paid exceptions use publisher domain and a curated issuer set, not Oxford in a title or any `.edu` suffix |
| Funding | A discount or tuition-only award could be described as full support | Separate funding categories; overclaims and unsupported amounts are held |
| Money | Currency substitution, invented fixed sum or omitted “up to” condition | Amount/currency evidence and conditional wording checked |
| Cost visibility | Deposits/visa exclusions could disappear inside shortened copy | Mandatory costs have their own visible, untruncated block |
| Coverage | Missing model indexes were silently saved as rejected | Every omitted/conflicting index is retryable; unsupported negative claims are reviewed |
| Ranking | Long private-event copy or a degree discount could outrank a funded fellowship | Program value, funding, issuer and urgency determine order; representative evidence quality remains separate |
| Intake cycle | Permanent URL/program identities could hide a newly announced year | New-year source revisions are re-read; same-program new intakes enter persisted review rather than silent duplicate rejection |
| Multilingual | Russian stems/Uzbek suffixes did not match word boundaries | Discovery handles common suffixes, Russian results, closed calls and deadlines |
| Dates | Ambiguous numeric format guessed; event date could keep expired applications alive | Ambiguity stays unknown; expiry considers both interpretations; event dates excluded |
| Renewal | An old closed cycle could hide a reopened call | Current open-call evidence is considered; official catalogue details are refreshed |
| Reminders | Legacy posted rows bypassed current eligibility/fee rules | Official evidence and the same publication policy revalidate reminders |
| Operations | A valid digest plus another unverifiable batch made the whole run fail | Verified partial success reports warnings; unknown candidates stay retryable |
| Deletion | User-deleted message still occupied the daily slot | Explicit, ID-checked deletion recovery archives the old intent and requeues only its records |

## Publication contract

The model returns a card or an exclusion for every index. Publishable cards need
structured assessments of applicant type, Uzbekistan eligibility, pre-existing
location requirements, open-call state, program type, funding, organizer and
mandatory charges. Scope, funding, call and cost excerpts are validated against
the supplied official evidence. Unicode presentation differences are normalized;
ordered verbatim list fragments may use semicolon separators. Invented wording,
amounts or omitted decisions do not become verified facts.

The model's conclusion is not the final publisher. `selection_policy.py` applies
independent rules, including explicit source exclusions, charge contradictions,
issuer exceptions and financial wording. A private event cannot gain publication
by calling itself a scholarship. A deposit does not erase a separate application
fee. Application-free wording needs its own supporting evidence.

User's explicit policy: reputable university/government application fees are
evaluated separately; paid private forums must not automatically publish. An
unrecognized paid issuer is reviewed, even with an academic-looking domain.
Known nonprofit refundable deposits are distinguished from application fees and
their conditions remain visible.

## Decision trail

- `publish`: passes policy and can compete for the digest.
- `reject`: a supported exclusion, rather than absent information.
- `review`: genuine uncertainty, paid/private policy or a new-intake conflict.
- `retry`: unreadable evidence, missing coverage, unsupported quotation or copy.
- `defer`: valid selection outside the daily message/request budget.

`selection_report.json` is an Actions artifact containing public-source titles,
URLs, stages and reasons. Review records use their own `urn:novagrants:review:`
identity with persisted reason/source evidence. They do not overwrite a public
grant and do not enter reminder queries. `tools/review_queue.py` reads them.

## Verification

The release test suite covers positive and negative country/location examples,
institution-only calls mentioning students, legitimate host offers, private fees,
academic exceptions, missing costs, invented amounts/currencies, maximum awards,
unknown/missing model decisions, ranking, multilingual discovery, reopening,
ambiguous dates, new intake conflicts, legacy reminders, delivery and deleted-post
recovery. Both supported Python versions and security/dependency CI are checked.

Live MCW evidence exposed and reproduced the truncation false negative: country
eligibility, covered flights, refundable $100 deposit, visa exclusions and the
December deadline now survive together. A live Groq screening selected the
eligible MCW case with these conditions. US-enrolment-only and paid-private test
cases were excluded/held. No benchmark calls published channel messages or
modified grant records. Final exact test counts, CI and production run links are
recorded in the release PR after browser-based deployment.

## Remaining operational boundaries

Official pages can be unavailable, incomplete or ambiguous. A missing condition
cannot be invented. Specific regional rules still need source support; this is
not a universal admissions/legal verifier. Same-URL annual intakes with legacy
history require confirmation before reusing a published identity. The existing
database access/RLS configuration is not changed by this selection release.
Unknown Telegram write results are held for reconciliation, not replayed.
These limits remain visible; a green workflow is not a claim of universal,
permanent bug-free operation.

## Production screening follow-up

The first full production run on the new policy, `43215990563`, intentionally
published nothing: Gemini exhausted its quota; a four-programme fallback request
failed strict JSON validation and hit the rate limit; other otherwise useful
cards had repairable public copy or unsupported quote formatting. The report
distinguished those causes. This was not a database failure and no delivery claim
was created.

The richer screening schema now receives one official programme per request.
The original two-programme smoke also reproduced the output-budget failure,
whereas the single NL Scholarship request returned a valid publishable card.
Retries now respect the editorial pacing interval too, rather than causing a
second request five seconds after an already costly failed generation.
Copy-only failures may use at most three small translation-repair requests per
process. Screening facts and evidence remain unchanged; repaired copy must pass
the same independent publication checks and preserve all numeric claims. Failed
repairs remain retryable. Ordered literal evidence fragments use the existing
supported-quote rule for eligibility too. Decision reasons are logged per input.
This correction does not lower eligibility or financial-evidence requirements.
