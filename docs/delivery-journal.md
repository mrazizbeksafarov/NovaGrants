# Daily delivery and recovery

The production path now reserves a digest before sending it. The reservation
key includes the configured channel, message kind and **Tashkent calendar day**.
Repeated manual runs and concurrent processes cannot create another daily digest.
Deadline reminders have a separate daily reservation.

## Storage

The existing `posted_grants` table already has unique `url` and `url_key` indexes
and text columns. Journal rows use `urn:novagrants:delivery:...` for both keys;
`source_url` holds the versioned JSON intent (blocks, HTML, grant save operations,
reminder URLs and count). No schema migration or access-policy change is required.
These rows are never `posted`, have `reminder_sent=true`, and cannot match normal
HTTP source keys. Grant statistics, deduplication and reminders exclude them.
This compatibility choice avoids requiring new database privileges at deployment.

States:

| State | Meaning | Automatic behavior |
|---|---|---|
| `delivery_prepared` | Complete intent saved; no send claimed | Resume the exact saved payload on the same day |
| `delivery_sending` | One process claimed the send | Stop and alert; do not resend |
| `delivery_sent` | Telegram acknowledged delivery | Retry database saves only, across day boundaries |
| `delivery_done` | Grant saves/reminder flags confirmed | Skip this kind for the rest of that day |

The claim is a conditional update from `prepared` to `sending`. Exactly one
updated row must be returned before Telegram can be called. A lost write response
stops the run. A definite Telegram rejection with no delivered parts releases the
claim to `prepared`. Timeouts, connection failures, server errors, partial delivery
and unexpected exceptions leave `sending` untouched.

Telegram send methods have no application idempotency key. Therefore this is a
conservative **at-most-once attempt after an uncertain result**, not a claim of
exactly-once delivery. A crash immediately before the HTTP request can also leave
an unresolved reservation; this favors avoiding duplicate public posts.

## Operator recovery

Inspect unresolved rows without changing anything:

```sql
select url_key, title, status, posted_date, source_url
from public.posted_grants
where status in ('delivery_sending', 'delivery_sent');
```

For `delivery_sending`, compare the saved content and time with the channel.
If the complete post is confirmed present, change **that exact row** to
`delivery_sent`; the next run repairs grant saves and finishes the journal.
If it is confirmed that no Telegram write happened, the row may be reset to
`delivery_prepared` for a same-day retry. If delivery cannot be determined, leave
it blocked. Do not delete or reset the journal merely to make a run green.
Never reset a partially delivered post for automatic replay.

Prepared rows from an earlier day are not automatically sent later. Their grants
remain unposted and can be selected by a new day's digest. Completed rows remain
as a durable audit trail. Keep the configured channel identifier stable; changing
from a username to numeric ID requires preserving/migrating the corresponding keys.

## Message budget and sharing

At most eight selected cards are considered for publication. The builder reduces
the selection until rich, legacy rich and HTML fallback **all fit one message**.
Deferred selections are not recorded as `skipped`; eligibility is not truncated to
force a fit. Oversized individual cards fail before a delivery claim is created.

The former `t.me/share/url` button shared a link, not the original message.
It has been removed. Native Telegram Forward remains available with channel
attribution; this bot does not set `protect_content`. There is no inline-button
action that opens native forwarding for an arbitrary existing post in the
[Bot API button contract](https://core.telegram.org/bots/api#inlinekeyboardbutton).

## Validation

Offline regressions cover failed database writes before/after Telegram, lost
acknowledgment writes, claim races, uncertain delivery across dates, reminder
recovery, Tashkent midnight, same-day suppression, nine selected cards, oversized
HTML, Groq-only link selection and invalid eligibility evidence.
