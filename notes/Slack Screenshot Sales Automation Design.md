# Slack Screenshot Sales Automation Design

**Status:** Implemented; confirmation pilot pending

**Date:** 2026-08-29

**Last updated:** 2026-09-01

## Objective

Add a private, local-first Slack intake workflow for two explicit screenshot actions:

- `sold`: reconcile visible Dofus Touch sale notifications with active Web UI
  listings, correct a matched listing's Sales Price when needed, and mark it sold.
- `market`: reconcile the player's own visible marketplace listings with active Web
  UI listings and add only missing craftable item-and-price occurrences.

The workflow reduces repeated data entry without allowing a vision model to decide
which business action to take or to write directly to SQLite. The existing FastAPI
Sales UI remains the system of record and the correction surface.

This design records the recommendations accepted through the `grill-me-yolo`
alignment on 2026-08-29. The local confirmation-required implementation now exists;
live provider evaluation, Slack setup, and the controlled pilot remain operational
gates. Marketplace image extraction stays disabled until its private labeled layout
sample is available.

## Success criteria

The pilot is successful when all of the following are true:

1. A permitted user can post one or more supported screenshots as one top-level
   message in the private `#dofus-touch` channel.
2. The user explicitly selects `sold` or `market` in the caption or through a bot
   button; image content never chooses the action.
3. The worker extracts visible rows, validates them against current SQLite state, and
   presents the proposed changes before any mutation.
4. Confirming a fully valid batch writes all of its changes in one SQLite transaction;
   rejecting, ambiguity, stale state, or any invalid row writes none of them.
5. Re-delivered Slack events and exact duplicate screenshots do not repeat mutations.
6. A `sold` batch never creates a listing, and a `market` batch never marks a listing
   sold, deletes a listing, or reprices one.
7. Screenshots, Slack identifiers, secrets, and raw model output remain local and do
   not enter Git, BigQuery, or dbt.
8. The existing manual Sales workflows continue to behave as before.

## Scope

### Included

- One private, manually created Slack channel named `#dofus-touch`.
- One allowlisted Slack workspace, channel, and user during the pilot.
- Top-level Slack messages containing PNG, JPEG, or WebP screenshots.
- One parent message, including all supported image attachments, as one atomic batch.
- Exact first-line caption actions `sold` and `market`, case-insensitive after
  trimming. Messages without one receive action-selection buttons.
- A dedicated local worker launched separately from the FastAPI web process.
- Durable SQLite intake, idempotency, retry, review, and audit state.
- Vision extraction through a local, ChatGPT-authenticated Codex CLI subprocess with
  structured output.
- A Slack preview with Confirm and Reject actions for the initial pilot.
- Exact item-name reconciliation against active Sales listings, with screenshot-led
  price correction for `sold` after exact-price matches are reserved.
- Existing latest-recipe and profession rules for deciding whether an item is
  craftable and in scope.
- Local evidence retention, pre-mutation SQLite backups, and operational logging.
- Generic, non-sensitive capture lineage on normalized sale listings for later
  BigQuery and dbt analysis.

### Deferred

- Reading arbitrary conversation or threaded replies as work requests.
- Multiple users, workspaces, channels, or role management.
- Public HTTP ingress, Slack HTTP Events API hosting, or a continuously hosted worker.
- Automatic item/catalog creation, recipe creation, recipe inference, fuzzy item
  matching, or guessed prices.
- Standalone repricing, `market` repricing, deleting listings, or treating an absent
  screenshot row as evidence that a Web UI listing was removed from the game.
- Processing other players' marketplace screens, chat messages, spreadsheets,
  receipts, videos, GIFs, PDFs, or unsupported image formats.
- Game-client automation, scraping, or external collection beyond screenshots the
  user explicitly posts.
- Fully autonomous mutation before action-specific evaluation gates are met.
- Scheduled BigQuery publication or dbt builds.

## Research findings

### Slack transport

Use Slack Bolt for Python with Socket Mode for the local pilot. Socket Mode receives
Events API and interactive payloads over a WebSocket and does not require a public
request URL, which fits the current loopback-only application boundary. Slack notes
that WebSocket disconnections are expected, so durable event intake and startup
catch-up are required rather than assuming a continuous connection.

Relevant primary sources:

- [Bolt for Python Socket Mode](https://docs.slack.dev/tools/bolt-python/concepts/socket-mode/)
- [HTTP request URLs compared with Socket Mode](https://docs.slack.dev/apis/events-api/comparing-http-socket-mode/)
- [Slack Events API delivery and retries](https://docs.slack.dev/apis/events-api/)
- [Slack message event](https://docs.slack.dev/reference/events/message/)
- [Slack file object and private download URLs](https://docs.slack.dev/reference/objects/file-object/)

The app needs only these pilot permissions:

- bot token scopes: `groups:history`, `files:read`, and `chat:write`
- app-level token scope: `connections:write`

The channel is private and the app is invited manually. The worker filters the exact
workspace, channel, and owner user before downloading an attachment. It acknowledges
Slack promptly after durable intake, then performs model and database work outside
the event callback. Startup calls conversation history from a persisted watermark to
recover messages missed during downtime. Slack event IDs and the parent message
identity are idempotency inputs because Events API delivery is retryable and
best-effort.

Socket Mode is a pilot choice, not a permanent production constraint. A later hosted
deployment should reconsider the HTTP Events API with signature verification.

### Vision extraction

Use the installed Codex CLI in non-interactive mode. The local bridge attaches
validated evidence files to `codex exec`, supplies the Pydantic JSON Schema through
`--output-schema`, and reads the final JSON from `--output-last-message`. Codex CLI
reuses its saved ChatGPT authentication, so this local pilot consumes subscription
usage and does not require an OpenAI API key.

Relevant primary sources:

- [Codex authentication](https://learn.chatgpt.com/docs/auth)
- [Codex non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode)
- [Codex developer commands](https://learn.chatgpt.com/docs/developer-commands?surface=cli)
- [Slack Bolt 1.30.0 on PyPI](https://pypi.org/project/slack-bolt/1.30.0/)

Each run is ephemeral, ignores user configuration and execution rules, uses the
read-only sandbox in a fresh temporary working directory, disables shell,
multi-agent, local-image-tool, and web-search access, and sets Codex's shell
environment inheritance to none. The subprocess itself receives an allowlist of only
the environment variables needed to locate Codex, its cached authentication, locale,
and certificates. It receives no Slack tokens, database variables, listing
identifiers, or mutation functions. Screenshot pixels are still sent to OpenAI and
must be treated as disclosed to the provider.

The blank model setting uses the subscription's current Codex CLI default. Model
choice remains evaluated configuration rather than a permanent domain rule; an
explicit model may be pinned only after passing the private gold-set evaluation.

## Explicit action contract

The requested action is established only by either:

1. the exact first non-empty caption line `sold` or `market`; or
2. an owner click on the corresponding Slack button.

Any additional caption text is non-authoritative context. A missing action leaves the
batch in `awaiting_action`. An unrecognized caption produces the same result. The
worker never infers an action from the screenshot or from model output. An owner
button click is acknowledged before processing, immediately replaces the action
buttons with a non-interactive hourglass status, and lets the eventual preview or
review result replace that same Slack message.

The extraction also reports a `screen_kind` of `sold_notification`,
`own_market_listings`, `other`, or `uncertain`. The batch requires manual review when
the requested action and screen kind disagree. This check is a safety constraint, not
an action selector.

## Capture unit and timestamps

One top-level Slack message is one capture batch. All supported images attached to
that parent message are ordered by their Slack file order and processed together.
Thread replies are ignored during the pilot.

The Slack parent-message timestamp is converted to UTC and used as:

- `date_sold` and the recipe-cost snapshot time for a `sold` batch;
- `selling_started_at` and linked price-observation time for listings created by a
  `market` batch.

This makes history catch-up deterministic. A `sold` timestamp earlier than the
matched listing's start time is invalid and requires review. Stored timestamps remain
UTC; the Web UI retains its current Pacific display behavior.

## Extraction contract

The structured model response contains:

```text
screen_kind
occurrences[]
  raw_item_name
  displayed_price_kamas
  image_number
  row_number
warnings[]
```

Occurrences preserve screenshot and top-to-bottom row order. Each visible listing
row is one occurrence, including repeated identical name-and-price pairs. Prices must
be positive whole kamas. The model does not normalize names, resolve catalog items,
decide craftability, or identify a database listing.

The validator applies the repository's existing whitespace-collapsed Unicode
case-folded exact-name normalization. Similarity can be included only as explanatory
review information; it never establishes identity.

The implementation cannot finalize this prompt or its row semantics until Gate 0
contains at least one private, labeled sample for each supported screen layout. This
is particularly important for confirming how duplicate rows, truncated names, and
any quantity markers appear in the actual client.

## Craftable and in-scope definition

An occurrence is actionable only when all of these conditions hold:

- the normalized name resolves to exactly one active catalog item;
- that item has a latest recipe;
- the latest recipe profession is one of `Tailor`, `Shoemaker`, or `Jeweller`; and
- the displayed asking price is a positive whole number.

These are pilot configuration values, loaded by the worker and displayed in the
preview. They are not inferred by the model. An exact catalog item whose latest
recipe is absent or outside the approved professions is reported and deterministically
ignored as out of scope; this matches the user's request to manage craftable items in
the approved professions. An unresolved or ambiguous name cannot be classified
safely and therefore sends the full batch to review. No row disappears silently.

## `sold` reconciliation

For every extracted in-scope occurrence:

1. Resolve the exact catalog item and displayed asking price.
2. Reserve active listings that already have the same item identity and asking price,
   oldest `selling_started_at`, then lowest internal ID, first.
3. Assign each remaining occurrence to the oldest remaining active listing for the
   exact item and propose changing its Sales Price to the screenshot price.
4. Reject the entire batch when there are fewer active item listings than screenshot
   occurrences, when any row is ambiguous, or when the timestamp predates a match.
5. On confirmation, re-run all checks in the write transaction to protect against
   stale previews.
6. Append one linked quantity-one `slack_sold_capture` price observation for each
   correction, update the matched listing price, set one shared `date_sold` from the
   Slack timestamp, and snapshot each recipe cost using only recipe and price
   information available at that timestamp. Missing historical cost coverage remains
   null.

The action never creates a listing to make a screenshot match. Extra active Web UI
listings that are not represented by the screenshot remain unchanged.

## `market` reconciliation

This action supports only a screenshot of the user's own active marketplace listings.
For every extracted in-scope `(item identity, displayed asking price)` pair:

1. Count its occurrences in the complete screenshot batch.
2. Count current active Web UI listings with that exact identity and price.
3. Propose `max(screenshot count - Web UI count, 0)` new listings.
4. Create each missing listing at the exact screenshot price, with one linked
   quantity-one append-only price observation whose source is
   `slack_market_capture`.

A different active price for the same item is a conflict requiring review; the worker
does not reprice it. Extra Web UI listings remain unchanged because an incomplete or
scrolled game screen is not evidence of removal. The action does not create catalog
items or recipes and does not mark anything sold.

An exact already-synchronized screenshot is a successful no-op and receives a receipt
describing that result.

## Human confirmation and autonomy gates

Initial operation is confirmation-required for both actions. The Slack preview shows:

- requested action and detected screen kind;
- observed timestamp and ordered source rows;
- exact catalog matches and craftable profession;
- proposed listing UUID-free descriptions, counts, and old-to-new price corrections;
- conflicts, out-of-scope rows, and warnings;
- Confirm and Reject buttons.

Only the allowlisted owner can confirm or reject. Confirmation is itself idempotent.
The preview never exposes internal primary keys, private download URLs, or model
payloads. Confirming or rejecting immediately replaces the interactive buttons with a
non-interactive decision state, and the terminal receipt updates that same preview
message. Selecting `sold` or `market` through the earlier action buttons follows the
same pattern: show a processing state immediately, remove stale controls, and reuse
the message for the next result.

`sold` and `market` have independent auto-commit flags, both false by default. An
action may graduate only after:

- the private labeled corpus for that action passes with zero false-positive
  mutations;
- at least 20 live confirmation-mode batches for that action complete with zero
  false-positive mutations; and
- an independent second extraction, using a separately phrased verification prompt,
  returns the exact same ordered occurrence list and compatible screen kind.

Any disagreement, warning, partial duplicate, or state conflict falls back to review.
Graduating one action does not graduate the other.

## Architecture

```text
private Slack #dofus-touch
          |
          | Socket Mode event / button payload
          v
  dedicated local capture worker
          |
          +--> durable capture inbox and local evidence
          |                 |
          |                 v
          |        Codex CLI vision extraction
          |                 |
          |                 v
          |       deterministic reconciliation
          |                 |
          +------> Slack preview / confirmation
                            |
                            v
             one SQLite write transaction
                            |
                            v
                  existing FastAPI Sales UI
                            |
                            v
             manual snapshot -> BigQuery -> dbt
```

The worker shares domain services and SQLite with FastAPI but has its own command,
configuration, and process lifetime. It is not mounted as a web router. Bolt owns
Slack transport, the Codex CLI adapter owns vision I/O, repositories own persistence,
and a capture service owns orchestration and validation.

Only one capture processor writes at a time during the pilot. SQLite remains in WAL
mode with its existing foreign-key and busy-timeout configuration.

## Operational data model

### `sale_capture_batches`

Durable intake and state-machine record:

- stable UUID and provider (`slack`)
- local workspace, channel, parent-message, event, and requester identifiers
- requested action and caption
- observed and received timestamps
- state, attempt count, next-attempt time, and expiring processing lease
- model, prompt, schema, and verification versions
- local structured extraction and validation payloads
- approving/rejecting user and decision timestamps
- terminal error code and redacted diagnostic message
- Slack preview and receipt identifiers/status

The provider/workspace/channel/parent-message identity is unique. Provider-specific
identifiers and payloads remain local and are excluded from analytical snapshots.

The state machine is:

```text
received -> awaiting_action -> queued -> extracting -> awaiting_confirmation
                                      \-> needs_review
awaiting_confirmation -> committing -> committed
                      \-> rejected
transient failure -> retry_wait -> queued
permanent failure -> failed
```

`awaiting_action`, `needs_review`, `committed`, `rejected`, and `failed` survive worker
restarts. An expired processing lease makes interrupted work eligible for recovery.
Slack preview/receipt delivery has a separate retry status so a post-commit Slack
failure never rolls back a successful database transaction.

### `sale_capture_files`

One row per ordered attachment:

- capture batch, attachment order, provider file identifier, MIME type, and byte size
- SHA-256 content hash and ignored local relative evidence path
- download, validation, retention, and purge timestamps/status

The worker accepts PNG, JPEG, and WebP up to 20 MB per file after verifying both
declared and decoded content. An exact repeat of a previously completed full hash set
is a no-op. A partially overlapping hash set requires review rather than guessing
which rows are new.

### `sale_capture_listing_actions`

Append-only local association between a capture and each affected `sale_listings` row:

- capture batch and sale listing
- action (`created` or `marked_sold`)
- effective timestamp and asking price evidenced at the action
- created timestamp

The capture/listing/action combination is unique. This table preserves lifecycle
history when a market capture creates a listing, a later capture marks it sold, the
user reopens it, and a still later capture marks it sold again.

### Sale-listing analytical lineage

Add nullable, provider-neutral current-lineage columns to `sale_listings`:

- `listing_source` and `listing_capture_uuid`
- `sale_source` and `sale_capture_uuid`

Existing records are backfilled with `manual` where the historical origin is known.
New manual UI actions set manual lineage; capture actions set a generic
`slack_market_capture` or `slack_sold_capture` source plus capture UUID. Reopening a
sale clears its current sale lineage along with `date_sold` and cost-at-sale; the
append-only local action history remains intact.

Only these generic fields are added to the operational BigQuery contract and dbt
sale models. Capture tables, Slack identifiers, screenshots, raw captions, and raw
model or validation payloads are never published.

## Transaction boundary

Current public Sales service methods own their commits. Implementation should extract
transaction-ready domain mutation primitives that flush but do not commit, while
leaving the existing public methods as commit-owning wrappers for web behavior.

For a confirmed capture:

1. Reload the batch and obtain an idempotent committing transition.
2. Re-run exact catalog, recipe, profession, active-listing, deterministic matching,
   price-correction, count, and timestamp validation.
3. Create and integrity-check a timestamped SQLite online backup in the ignored
   backup directory.
4. Apply all listing, price-observation, cost-snapshot, current-lineage, action-history,
   and batch-status writes in one database transaction.
5. Commit once, then enqueue the Slack receipt separately.

Any validation failure or write conflict rolls back the complete batch. Backups use
SQLite's online backup API rather than copying a live database file.

## Idempotency and retries

- Duplicate Slack delivery: return the persisted batch by unique parent identity.
- Repeated button click: return the existing decision or committed result.
- Exact repeated full screenshot hash set: successful no-op with a link to the prior
  local capture UUID.
- Partial hash overlap: `needs_review`.
- Transient Slack download, Codex CLI execution, or Slack response error: capped exponential retry
  with jitter and a persisted next-attempt time.
- Invalid image, schema-invalid extraction, action/screen mismatch, ambiguity, or
  database conflict: no automatic retry; require review.
- Expired worker lease: recover safely from the last durable state.

Logging includes capture UUID, state transitions, counts, durations, retry category,
and provider request IDs where safe. It excludes tokens, private URLs, screenshot
bytes, captions, item payloads, and raw structured outputs.

## Evidence, privacy, and secrets

Downloaded evidence lives under ignored `data/app/slack_sales_evidence/`. Screenshots
for terminal captures are retained for 90 days and then purged; evidence still needed
for an open review is retained until the review becomes terminal. Content hashes and
generic capture/action provenance remain permanent in local SQLite.

Private labeled evaluation data also lives below this ignored boundary. Tests in Git
use invented fixtures and mocked image/model responses only.

Worker-only environment configuration contains the Slack bot token, Slack app token,
allowlisted IDs, evidence directory, Codex binary/model/timeout, and the two
independent auto-commit flags. ChatGPT authentication remains in the Codex CLI's
credential store. Secret values are never accepted through web requests, written to
tracked files, printed, or loaded as required global FastAPI settings. A missing
worker secret or unavailable ChatGPT login prevents only the worker command from
starting.

## Manual Slack setup outline

Implementation documentation will guide the owner to:

1. create the private `#dofus-touch` channel;
2. create a Slack app from a tracked, secret-free manifest;
3. grant only the listed scopes and enable Socket Mode and interactivity;
4. subscribe to the private-channel message event;
5. install the app, invite it to the channel, and record the workspace, channel, and
   owner IDs outside Git;
6. create separate bot and app tokens outside Git; and
7. run the worker locally after the database migration and private evaluation gate.

No Slack workspace or app configuration is changed as part of this design phase.

## Rollout gates

### Gate 0: private examples and gold labels

- Provide at least one real screenshot for each supported layout: a sale-notification
  screen and the user's own marketplace listing screen.
- Keep the files and expected structured JSON outside Git.
- Confirm row boundaries, price rendering, truncation, duplicates, scroll behavior,
  and any quantity indicators.
- Collect additional difficult examples before considering autonomy.

### Gate 1: offline extraction evaluation

- Run the versioned extraction adapter against the private corpus without database
  writes.
- Require exact screen-kind, ordered normalized name, price, and occurrence-count
  agreement for every mutation-eligible example.
- Treat a false positive as a release blocker; false negatives remain reviewable.

### Gate 2: dry-run Slack integration

- Receive real messages, persist intake, extract, reconcile, and post previews.
- Disable every mutation path.
- Verify restart recovery, duplicates, retries, authorization, unsupported files, and
  history catch-up.

### Gate 3: confirmation-required pilot

- Enable explicit owner confirmation.
- Create a backup and revalidate immediately before every atomic write.
- Record corrections and false-positive/false-negative outcomes separately by action.

### Gate 4: guarded action-specific autonomy

- Meet the corpus and 20-live-batch gates for one action.
- Enable its flag only, retain independent verification, backups, receipts, and review
  fallback, and keep the other action confirmation-required.

## Important risks and controls

| Risk | Control |
| --- | --- |
| Wrong action inferred | Action comes only from exact caption or owner button. |
| OCR/model hallucination | Structured extraction, exact deterministic validation, confirmation, gold-set evaluation. |
| Duplicate Slack delivery | Durable unique message identity and idempotent transitions. |
| Stale preview | Full revalidation inside the write transaction. |
| Partial batch mutation | One transaction for all domain and audit writes. |
| Wrong duplicate listing selected | Reserve oldest exact-price matches first, then use the oldest remaining exact-item listing. |
| Market screenshot treated as authoritative absence | Add missing exact counts only; never remove extras. |
| Incorrect sold price correction | Exact item identity, owner-visible old-to-new preview, confirmation, backup, and atomic write. |
| Private data leak | Ignored local evidence, redacted logs, `store: false`, no raw capture publication. |
| Worker crash | Durable states, leases, startup history catch-up, retry queue. |
| Bad automated write | Pre-mutation online backup and existing Web UI correction path. |
| Scope expansion into game automation | Screenshot intake only; no game-client control or scraping. |

## Final decisions

- Keep FastAPI and Slack worker processes separate while sharing tested domain
  services and SQLite.
- Use direct SDK integrations, not a general-purpose agent framework.
- Let the model extract pixels only; deterministic code owns identity, craftability,
  reconciliation, authorization, and writes.
- Require exact names, active-item counts, supported latest-recipe professions, and
  message-level atomicity; use a confirmed `sold` screenshot price to correct the
  deterministically matched listing.
- Preserve full local action history and publish only generic normalized lineage.
- Begin with confirmation for both actions and graduate them independently, if ever.
- Do not implement until Gate 0 provides real private samples for both layouts.
