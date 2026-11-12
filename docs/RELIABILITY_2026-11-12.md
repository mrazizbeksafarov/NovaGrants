# Reliability hardening after the delivery incident

This release adds recovery for known temporary service failures and preserves
strict stops when delivery or eligibility cannot be established. It does not
claim that third-party services cannot fail or that every future source wording
can be interpreted without error.

## Database and delivery

`resilience.execute` makes at most three identical database requests, with 1/3
second delays, for transport errors, temporary server errors and connection pool
unavailability. Authorization, schema and uniqueness errors are not treated as
temporary. The existing writer reconciles both unique identities after insertion
races or lost responses.

Journal claims now carry a random ownership token in the journal row's
`fingerprint` field. If a conditional update committed but its response was lost,
the caller reads the row and accepts only its own token and expected state. A
different process's claim cannot grant permission to send. Existing journal rows
remain compatible; no schema migration is needed. The token is used only for
namespaced journal rows, which are excluded from posted-grant fingerprint checks.

The supervisor restarts a run at most three times for a known temporary database
failure, after 5/15 second delays. Journal recovery determines whether to finish
database saves or resume a definitely unattempted send. It never restarts a
Telegram `DeliveryUncertain` or journal `UncertainDelivery` exception. Truncated
Telegram response streams, malformed success bodies and missing sent-message
identifiers are also uncertain, rather than a reason to send an HTML duplicate.

## Source isolation and official eligibility

A broken adapter, malformed row or exceptional resolver no longer discards
healthy candidates from other sources. Temporary problems are summarized in the
existing administrator report. Unknown candidates are not saved as rejected.

Before editorial selection, up to 32 unique candidate URLs are read with six
workers. A generic official homepage may follow one title-matching link within
the same organisation to find the actual programme announcement. Aggregator
redirects, unreadable pages, challenge screens and pages without eligibility
evidence are deferred, not accepted from an aggregator's claim alone.

An explicit foreign-enrolment requirement on the official page excludes the
programme from the Uzbekistan-based audience. Otherwise, the editor receives
official page evidence in place of the aggregator summary, up to 6,000 characters.
The extractor prioritizes late exclusions and applicant costs, including bullets
following a "Costs Not Covered" heading. Editorial batches are limited to eight
items and approximately 12,000 input characters so the expanded evidence does not
silently disappear or balloon every request. At most eight editorial batches are processed;
overflow is not marked rejected. A model that reaches its transport timeout is
not repeatedly waited for in subsequent batches of the same process. Existing
quote and copy validation still applies to both providers. If an entire official-evidence stage is
unavailable, no unverified public post is emitted and the run reports the problem.

## Deployment protection

Production Python is pinned to the tested 3.13.18 patch release. CI still checks
Python 3.11 and 3.13. GitHub-maintained checkout, setup-python and upload-artifact
actions are pinned to the verified commit SHAs of releases v7.0.1, v7.1.0 and
v7.0.2. Pip has the same bounded version range as CI. Dependency versions remain
constrained by `constraints.txt`.

A dependency-free, fixed-host HTTPS alert can notify the existing admin if
installation or tests prevent the Python bot from starting. It does not replace
the bot's own failure report, print tokens or turn a failed workflow green.
CI now rejects medium/high Bandit findings in runtime modules and this alert.
Required CI checks on `main` are recorded in the release PR after verification.

## Evidence

- Offline fault injection covers committed writes with lost responses at claim,
  send acknowledgment and completion; process ownership races; bounded persistent
  outages; unsupported schema; unknown Telegram outcomes; malformed adapters;
  partial official-page outages and failed startup alerts.
- An isolated live Supabase probe committed its claim, intentionally lost the
  acknowledgment, confirmed ownership and completed one simulated send without
  replay. It made zero Telegram calls and its database row was removed.
- Live official-page checks rejected Stanford's US-enrolment requirement and
  discovered MCW's actual 2027 announcement from its homepage. MCW's $100 deposit
  and passport/visa exclusions survived extraction. A separate unreachable forum
  page was deferred rather than approved from secondary claims.
- Final CI, end-to-end dry-run and production resumption links are recorded in
  the release PR. A successful already-completed-day resumption does not by itself
  exercise new-source collection; the dry-run and fault tests cover that path.
