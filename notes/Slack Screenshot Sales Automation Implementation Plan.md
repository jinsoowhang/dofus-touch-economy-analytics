# Slack Screenshot Sales Automation Implementation Plan

**Goal:** Add a private local Slack screenshot workflow that safely performs the
explicit `sold` and `market` reconciliation actions approved in
`notes/Slack Screenshot Sales Automation Design.md`.

**Architecture:** A dedicated Slack Bolt Socket Mode worker durably records authorized
top-level image messages in operational SQLite, asks a local, ChatGPT-authenticated
Codex CLI subprocess only for structured pixel extraction, and applies deterministic
repository and service rules. FastAPI remains the system-of-record UI. Every confirmed
batch is revalidated, backed up, and committed atomically. Provider-private capture
data remains local; only generic sale-listing lineage enters the analytical contract.

**Tech stack:** Python 3.12, uv, Slack Bolt for Python 1.30.0, Codex CLI,
Pydantic 2, SQLAlchemy 2, Alembic, SQLite, Pytest, FastAPI, BigQuery, dbt Core, and
DuckDB.

This document remains the detailed acceptance map; checkbox state is not the
implementation record. As of 2026-08-29, Tasks 1 through 10 and the code/documentation
portion of Task 11 are implemented with synthetic tests. Gate 0 has a private labeled
`sold` sample but no marketplace sample. Live Codex evaluation, Slack dry-run,
confirmation pilot, and every autonomy gate remain incomplete.

---

## Working rules

- Read the approved design before each task and do not broaden its single-user,
  private-channel scope.
- Gate 0 is mandatory before finalizing prompts or claiming screenshot support.
- Use `uv`; add dependencies through `uv add`, never `pip`.
- Write each focused test first, observe the expected failure, implement only the
  behavior under test, and rerun focused regression tests.
- Real screenshots, gold labels, Slack payloads, tokens, local databases, backups,
  and model responses stay under ignored local paths and never become test fixtures.
- Synthetic tests may use invented filenames, IDs, item names, and structured model
  responses. They must not reproduce private screenshots.
- Keep Slack transport in the worker adapter, vision transport in the Codex CLI adapter,
  persistence in repositories, and reconciliation and mutation rules in services.
- Never give the model database tools or let it select `sold` versus `market`.
- Do not add request-time DuckDB or BigQuery writes.
- Do not weaken the existing exact schema or forbidden-public-file checks to make new
  files pass.
- Before each commit, run focused tests, Ruff on changed Python, `git diff --check`,
  `git diff --cached --check`, and the public-file check.
- Use one atomic commit per task. Do not stage unrelated user changes.
- Run `./scripts/check.sh` before the confirmation-required pilot is considered ready.
- At each implementation session end, update `MEMORY.md` and the dated session note.

## Planned file map

Names may move only when an existing module boundary clearly owns the behavior.

```text
pyproject.toml
uv.lock
.env.example                                      public-safe variable names only
data/app/README.md                                local capture/evidence boundary
docs/slack-screenshot-sales-setup.md              owner setup and runbook
docs/slack-app-manifest.yml                       secret-free Slack app manifest
migrations/versions/
  0009_sale_capture_audit.py                      local capture tables
  0010_sale_listing_capture_lineage.py            nullable analytical lineage
src/dofus_touch_economy/
  capture_config.py                               worker-only environment settings
  capture_schemas.py                              actions and structured extraction
  capture_evidence.py                             validated files, hashing, retention, backup
  capture_vision.py                               Codex CLI structured-output adapter
  slack_sales_worker.py                           Slack filters, buttons, history, receipts
  cli.py                                          dedicated worker/evaluation commands
  models.py                                       capture tables and listing lineage
  analytics_snapshot.py                           generic listing lineage contract
  repositories/
    sale_captures.py                              durable state, leases, idempotency, audit
    sales.py                                      bulk exact active-match queries
  services/
    sale_captures.py                              reconciliation and orchestration
    sales.py                                      transaction-ready mutation primitives
scripts/
  evaluate_sale_capture_vision.py                 private offline gold-set evaluation
models/staging/stg_operational__sale_listings.sql
models/marts/fct_sales.sql
models/staging/staging.yml
models/marts/marts.yml
seeds/local_operational/raw_sale_listings.csv
tests/python/
  test_capture_config.py
  test_capture_evidence.py
  test_capture_models.py
  test_sale_capture_repository.py
  test_sale_capture_service.py
  test_capture_vision.py
  test_slack_sales_worker.py
  test_sales.py
  test_migrations.py
  test_analytics_snapshot.py
  test_cli.py
```

## Task 0: Establish the private screenshot contract

**Owner input required:** real screenshots cannot be derived from the repository.

- [ ] Create ignored `data/app/slack_sales_evidence/gold/` locally.
- [ ] Add at least one unedited example of a Dofus Touch sold-notification screen.
- [ ] Add at least one unedited example of the user's own active-market-listings
  screen.
- [ ] Add adjacent local JSON labels containing screen kind and the ordered visible
  raw item names and whole-kama prices. Use no database UUIDs.
- [ ] Record whether screenshots can contain multiple panels, truncated item names,
  repeated identical rows, stack or lot quantities, partially visible rows, scroll
  indicators, notifications, or overlaid UI.
- [ ] Confirm that one visible marketplace row represents one desired Web UI listing.
  If it does not, stop and revise the approved action contract before implementation.
- [ ] Verify the files are ignored with `git check-ignore -v` and absent from
  `git status --short`.

**Exit condition:** both layouts and their exact row semantics are understood. This
task has no commit because all artifacts are private.

## Task 1: Add worker dependencies and isolated configuration

**Files:**

- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `.env.example`
- Modify: `data/app/README.md`
- Create: `src/dofus_touch_economy/capture_config.py`
- Create: `tests/python/test_capture_config.py`
- Modify: `tests/python/test_documented_commands.py`

- [ ] Write tests showing that normal FastAPI settings still load without Slack
  secrets or Codex CLI.
- [ ] Test a separate capture-worker settings loader that requires and redacts
  `DOFUS_SLACK_BOT_TOKEN` and `DOFUS_SLACK_APP_TOKEN` only when the worker starts.
- [ ] Test exact workspace, channel, and owner IDs; `data/app/slack_sales_evidence`;
  the Codex binary, subscription-default model, 180-second timeout, the three approved
  professions, 20 MB, 90 days, and false independent `sold`/`market` auto-commit
  flags as defaults.
- [ ] Observe the focused tests fail because the worker settings do not exist.
- [ ] Add `slack-bolt==1.30.0` through uv and document Codex CLI as an external local
  prerequisite; do not add the OpenAI Python SDK.
- [ ] Implement the worker-only loader without importing it from FastAPI app startup.
- [ ] Add only public-safe variable names and non-secret defaults to `.env.example`;
  never add token-shaped example values.
- [ ] Document the ignored evidence directory in `data/app/README.md`.
- [ ] Run:

  ```bash
  uv sync --locked --all-groups
  uv run pytest tests/python/test_capture_config.py \
    tests/python/test_config_database.py \
    tests/python/test_documented_commands.py -v
  uv run ruff check src/dofus_touch_economy/capture_config.py \
    tests/python/test_capture_config.py
  uv run python scripts/check_public_files.py
  ```

- [ ] Commit: `build: add isolated Slack capture worker configuration`

## Task 2: Add local capture and action-history tables

**Files:**

- Create: `migrations/versions/0009_sale_capture_audit.py`
- Modify: `src/dofus_touch_economy/models.py`
- Modify: `tests/python/test_migrations.py`
- Create: `tests/python/test_capture_models.py`

- [ ] Write populated upgrade tests proving migration `0009` preserves existing
  items, price observations, and sale listings.
- [ ] Write model tests for `sale_capture_batches`, `sale_capture_files`, and
  `sale_capture_listing_actions` foreign keys, uniqueness, allowed values, timestamp
  pairs, and positive sizes/prices.
- [ ] Cover the lifecycle where one listing is created by one capture, marked sold by
  another, reopened, and marked sold by a third; action history must remain append-only.
- [ ] Observe tests fail because the tables and models do not exist.
- [ ] Add a direct additive migration. Do not batch-rebuild referenced tables while
  foreign keys are enabled.
- [ ] Implement the three SQLAlchemy models and relationships with provider-neutral
  UUIDs and local Slack identifiers.
- [ ] Constrain capture states, requested actions, file statuses, receipt statuses,
  and listing actions to the approved values. Add the unique provider/workspace/
  channel/parent-message key and the unique capture/listing/action key.
- [ ] Keep JSON payloads and private identifiers out of `analytics_snapshot.py`.
- [ ] Run:

  ```bash
  uv run pytest tests/python/test_migrations.py \
    tests/python/test_capture_models.py -v
  uv run ruff check src/dofus_touch_economy/models.py \
    migrations/versions/0009_sale_capture_audit.py \
    tests/python/test_capture_models.py tests/python/test_migrations.py
  ```

- [ ] Commit: `feat: add local screenshot capture audit schema`

## Task 3: Add generic sale-listing lineage end to end

**Files:**

- Create: `migrations/versions/0010_sale_listing_capture_lineage.py`
- Modify: `src/dofus_touch_economy/models.py`
- Modify: `src/dofus_touch_economy/analytics_snapshot.py`
- Modify: `src/dofus_touch_economy/bigquery_loader.py` if schema-append tests require it
- Modify: `models/staging/stg_operational__sale_listings.sql`
- Modify: `models/staging/staging.yml`
- Modify: `models/marts/fct_sales.sql`
- Modify: `models/marts/marts.yml`
- Modify: `seeds/local_operational/raw_sale_listings.csv`
- Modify: `tests/python/test_migrations.py`
- Modify: `tests/python/test_analytics_snapshot.py`
- Modify or create focused dbt singular tests only if a generic invariant is
  insufficient

- [ ] Write migration tests for nullable `listing_source`, `listing_capture_uuid`,
  `sale_source`, and `sale_capture_uuid`, including populated dependent rows.
- [ ] Write exact snapshot-contract and BigQuery append-only evolution tests for the
  four nullable columns.
- [ ] Extend the synthetic sale seed with manual and capture-lineage examples, then
  add staging and `fct_sales` tests proving lineage passes through without exposing
  Slack identifiers or capture payloads.
- [ ] Observe focused tests or dbt parsing fail before changing the contract.
- [ ] Add the nullable columns and backfill known existing local rows to `manual`
  without making the BigQuery additions required.
- [ ] Update only the normalized sale-listing snapshot contract. Do not add any local
  capture table to `OPERATIONAL_TABLES`.
- [ ] Keep existing model grain and measures unchanged.
- [ ] Run:

  ```bash
  uv run pytest tests/python/test_migrations.py \
    tests/python/test_analytics_snapshot.py -v
  DO_NOT_TRACK=1 uv run dbt seed --full-refresh --profiles-dir .
  DO_NOT_TRACK=1 uv run dbt build --select \
    stg_operational__sale_listings+ --profiles-dir .
  DO_NOT_TRACK=1 uv run sqlfluff lint \
    models/staging/stg_operational__sale_listings.sql \
    models/marts/fct_sales.sql
  ```

- [ ] Commit: `feat: expose generic sale capture lineage`

## Task 4: Implement durable intake, idempotency, and leases

**Files:**

- Create: `src/dofus_touch_economy/repositories/sale_captures.py`
- Create: `tests/python/test_sale_capture_repository.py`

- [ ] Test idempotent insert by provider/workspace/channel/parent message.
- [ ] Test ordered file manifests, content-hash lookup, exact complete hash-set
  duplicate detection, and partial-overlap review detection.
- [ ] Test valid state transitions, invalid transition rejection, owner decisions,
  single-confirm behavior, and committed-result replay.
- [ ] Test claiming one oldest eligible batch, lease exclusion, expired-lease recovery,
  capped attempts, and persisted retry times.
- [ ] Test receipt retry state separately from domain state.
- [ ] Observe tests fail because the repository does not exist.
- [ ] Implement focused bulk queries and conditional updates; do not load screenshot
  bytes into SQLite.
- [ ] Ensure every transition uses current persisted state in its predicate so
  competing clicks or workers cannot both succeed.
- [ ] Run:

  ```bash
  uv run pytest tests/python/test_sale_capture_repository.py -v
  uv run ruff check src/dofus_touch_economy/repositories/sale_captures.py \
    tests/python/test_sale_capture_repository.py
  ```

- [ ] Commit: `feat: add durable sale capture inbox`

## Task 5: Add evidence validation, retention, and online backup

**Files:**

- Create: `src/dofus_touch_economy/capture_evidence.py`
- Create: `tests/python/test_capture_evidence.py`

- [ ] Test streaming download to a temporary file, a 20 MB hard cap, MIME and decoded
  format agreement, supported PNG/JPEG/WebP formats, SHA-256 calculation, atomic
  placement, and cleanup after failure.
- [ ] Use fully synthetic minimal images generated in the test, not private evidence.
- [ ] Test that only terminal evidence older than 90 days is purged and open-review
  evidence is retained.
- [ ] Test SQLite's online backup API against a live WAL database, then assert
  `PRAGMA integrity_check` is `ok` for the result.
- [ ] Observe tests fail before implementing the evidence service.
- [ ] Implement path containment so a provider filename cannot escape the configured
  ignored root. Logs and exceptions must not contain bearer URLs or bytes.
- [ ] Keep the Slack-authenticated HTTP call injectable; this module validates a byte
  stream and does not know Bolt events.
- [ ] Run:

  ```bash
  uv run pytest tests/python/test_capture_evidence.py -v
  uv run ruff check src/dofus_touch_economy/capture_evidence.py \
    tests/python/test_capture_evidence.py
  ```

- [ ] Commit: `feat: add private capture evidence safeguards`

## Task 6: Make Sales mutations composable without changing Web UI behavior

**Files:**

- Modify: `src/dofus_touch_economy/services/sales.py`
- Modify: `src/dofus_touch_economy/repositories/sales.py`
- Modify: `tests/python/test_sales.py`
- Modify: `tests/python/test_web.py`
- Modify: `tests/python/test_api.py` only if its regression coverage is affected

- [ ] Add regression tests proving current start, bulk start, mark sold, bulk mark
  sold, reopen, duplicate, update, and failure behavior remains unchanged.
- [ ] Add service tests for caller-supplied UTC start/sale times and source lineage,
  with a flush-only mutation primitive that does not commit.
- [ ] Test that capture-created linked price observations use quantity one, the exact
  supplied time and price, current market context, and source
  `slack_market_capture`.
- [ ] Test sold cost snapshots use only information available at the supplied Slack
  time and remain null when historical coverage is incomplete.
- [ ] Test reopening clears current `sale_source` and `sale_capture_uuid` together
  with sale time and cost while leaving capture action history untouched.
- [ ] Observe the new focused tests fail.
- [ ] Extract private transaction-ready primitives; keep existing public methods as
  commit-owning wrappers using `datetime.now(UTC)` and manual lineage.
- [ ] Add a bulk repository query for active exact item-and-price candidates ordered
  oldest first. Avoid per-row queries.
- [ ] Run:

  ```bash
  uv run pytest tests/python/test_sales.py tests/python/test_web.py \
    tests/python/test_api.py -v
  uv run ruff check src/dofus_touch_economy/services/sales.py \
    src/dofus_touch_economy/repositories/sales.py tests/python/test_sales.py
  ```

- [ ] Commit: `refactor: make sales mutations capture-transaction ready`

## Task 7: Implement deterministic capture reconciliation and atomic commits

**Files:**

- Create: `src/dofus_touch_economy/capture_schemas.py`
- Create: `src/dofus_touch_economy/services/sale_captures.py`
- Create: `tests/python/test_sale_capture_service.py`

- [ ] Test caption parsing: exact first non-empty `sold` or `market`; every other
  caption awaits an owner selection.
- [ ] Test action/screen-kind agreement and the approved ordered extraction schema.
- [ ] Test exact normalized catalog resolution, latest recipe selection, approved
  profession filtering, positive whole prices, deterministic reporting and exclusion
  of exact out-of-scope items, and review of every unresolved or ambiguous row.
- [ ] Test `sold` one-to-one matching, repeated occurrence counts, oldest-identical
  selection, insufficient matches, extra active listings left alone, timestamp before
  start, and no fabricated listings.
- [ ] Test `market` exact count differences, creation of missing occurrences only,
  already-synchronized no-op, different-price conflict, duplicate screenshot rows,
  extra Web UI listings left alone, and no repricing/deletion/sale mutation.
- [ ] Test message-level atomicity by injecting a stale-state conflict after preview
  and asserting zero listing, observation, lineage, action-history, or committed-state
  changes.
- [ ] Test a successful confirmation creates a valid backup before mutation, rechecks
  state, performs all writes and the capture transition in one commit, and leaves the
  Slack receipt pending outside the transaction.
- [ ] Observe tests fail before the capture service exists.
- [ ] Implement separate pure planning functions for `sold` and `market`, returning a
  preview with no side effects.
- [ ] Implement one confirmation command that reloads and revalidates the persisted
  extraction before using Task 6 primitives and recording action history.
- [ ] Do not accept ad hoc exclusions in the confirmation command. Predefined exact
  non-craftable or unapproved-profession rows remain reported but out of scope; an
  unresolved, ambiguous, or invalid in-scope row makes the complete batch
  `needs_review`.
- [ ] Run:

  ```bash
  uv run pytest tests/python/test_sale_capture_service.py \
    tests/python/test_sales.py -v
  uv run ruff check src/dofus_touch_economy/capture_schemas.py \
    src/dofus_touch_economy/services/sale_captures.py \
    tests/python/test_sale_capture_service.py
  ```

- [ ] Commit: `feat: reconcile screenshot sales atomically`

## Task 8: Add the evaluated vision extraction adapter

**Gate:** Task 0 must be complete before the prompt is finalized.

**Files:**

- Create: `src/dofus_touch_economy/capture_vision.py`
- Create: `tests/python/test_capture_vision.py`
- Create: `scripts/evaluate_sale_capture_vision.py`
- Modify: `src/dofus_touch_economy/cli.py`
- Modify: `pyproject.toml`
- Modify: `tests/python/test_cli.py`

- [ ] Define versioned primary and verification prompts from the observed private UI
  layouts. Require transcription, not catalog correction or business decisions.
- [ ] Test that the adapter uses `codex exec`, supported image paths, ephemeral
  execution, ignored user config/rules, disabled tools, a read-only sandbox, no shell
  environment inheritance, strict JSON Schema output, and a bounded timeout.
- [ ] Test schema rejection for missing names, non-positive/non-integral prices,
  invalid image/row positions, unknown screen kinds, and prose outside the contract.
- [ ] Test that the Codex subprocess receives no Slack bearer URL, database
  identifiers, secrets, or mutation tools.
- [ ] Test redacted transient versus permanent error classification and capture of
  safe request/model/prompt-version metadata.
- [ ] Test the independent verification path compares the exact ordered occurrence
  list and compatible screen kind rather than model confidence.
- [ ] Observe tests fail before implementing the adapter.
- [ ] Implement one injectable synchronous subprocess boundary; do not add an agent
  framework or API client.
- [ ] Add a read-only evaluation command that loads ignored screenshots and labels,
  performs no database writes, and reports exact-match metrics separately for `sold`
  and `market`.
- [ ] Run unit tests with a fake subprocess runner, then run the private evaluation
  with the owner's ChatGPT-authenticated Codex CLI.
- [ ] Record prompt/model versions and aggregate results in the dated session note,
  never the screenshots or extracted private rows.
- [ ] Commit: `feat: add structured screenshot extraction`

## Task 9: Add authorized Slack intake and interactive previews

**Files:**

- Create: `src/dofus_touch_economy/slack_sales_worker.py`
- Create: `tests/python/test_slack_sales_worker.py`

- [ ] With mocked Bolt and Slack clients, test exact workspace/channel/owner
  allowlisting before download or persistence of actionable content.
- [ ] Test bot messages, threads, edits, deletes, messages without images, and
  unsupported file types are ignored or answered without mutation as designed.
- [ ] Test one parent with multiple ordered images becomes one batch.
- [ ] Test the event callback acknowledges after idempotent durable intake and before
  download, vision, or database reconciliation.
- [ ] Test private file download uses the bot bearer token without logging the URL or
  token.
- [ ] Test missing caption buttons, explicit action captions, owner-only action clicks,
  owner-only Confirm/Reject, repeated clicks, and UUID-free preview content.
- [ ] Test action/screen mismatch, conflicts, unsupported images, and unresolved rows
  render review receipts without change buttons; exact out-of-scope rows remain
  visible but do not prevent a valid preview.
- [ ] Observe tests fail before implementing the Bolt adapter.
- [ ] Keep all database and Codex CLI calls outside Bolt event handlers; handlers enqueue
  or decide existing durable batches only.
- [ ] Escape all extracted text before Block Kit rendering and cap preview length with
  an explicit overflow summary.
- [ ] Run:

  ```bash
  uv run pytest tests/python/test_slack_sales_worker.py -v
  uv run ruff check src/dofus_touch_economy/slack_sales_worker.py \
    tests/python/test_slack_sales_worker.py
  ```

- [ ] Commit: `feat: add private Slack screenshot intake`

## Task 10: Add worker processing, catch-up, retries, and receipts

**Files:**

- Modify: `src/dofus_touch_economy/slack_sales_worker.py`
- Modify: `src/dofus_touch_economy/cli.py`
- Modify: `pyproject.toml`
- Modify: `tests/python/test_slack_sales_worker.py`
- Modify: `tests/python/test_cli.py`
- Modify: `tests/python/test_documented_commands.py`

- [ ] Test startup history catch-up from a persisted high-water mark, pagination,
  overlap with live delivery, and chronological durable intake.
- [ ] Test the single serial processor, lease renewal/recovery, bounded exponential
  retry with jitter, max attempts, and permanent `needs_review`/`failed` outcomes.
- [ ] Test restart at every durable state, especially after domain commit but before a
  Slack success receipt.
- [ ] Test receipts retry independently and never repeat listing mutations.
- [ ] Test confirmation mode is the default even if the model extraction succeeds.
- [ ] Test graceful shutdown stops new claims without interrupting a SQLite commit.
- [ ] Observe tests fail before adding orchestration and the CLI entry point.
- [ ] Add `dofus-slack-worker` as a dedicated process command. It must migrate nothing
  automatically and must fail clearly when SQLite is below the required revision.
- [ ] Add structured redacted logging for capture UUID, state, counts, durations, and
  safe request IDs only.
- [ ] Run:

  ```bash
  uv run pytest tests/python/test_slack_sales_worker.py \
    tests/python/test_cli.py tests/python/test_documented_commands.py -v
  uv run ruff check src/dofus_touch_economy/slack_sales_worker.py \
    src/dofus_touch_economy/cli.py tests/python/test_slack_sales_worker.py \
    tests/python/test_cli.py
  ```

- [ ] Commit: `feat: run durable Slack sale capture worker`

## Task 11: Document and prove the dry-run deployment

**Files:**

- Create: `docs/slack-screenshot-sales-setup.md`
- Create: `docs/slack-app-manifest.yml`
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/data-contract.md`
- Modify: `docs/operational-bigquery-ingestion.md`
- Modify: `data/app/README.md`
- Modify: `tests/python/test_documented_commands.py`
- Modify: `tests/python/test_check_public_files.py` only if a new policy assertion is
  needed

- [ ] Create a secret-free Slack manifest with Socket Mode, interactivity,
  `message.groups`, `groups:history`, `files:read`, `chat:write`, and the documented
  app-level `connections:write` token step.
- [ ] Document private channel creation, app installation/invitation, ID discovery,
  token storage, migration, worker startup, shutdown, evidence retention, review
  states, corrections, and token revocation.
- [ ] Document that Slack timestamps become effective sale/listing times and that
  history catch-up can make backdated changes only after confirmation.
- [ ] Document each action with examples that use invented item names only.
- [ ] Document `sold` exact matching, `market` additive count reconciliation, approved
  professions, atomic rejection, and the fact that no game-client automation occurs.
- [ ] Document normalized lineage publication and the capture data that remains local.
- [ ] With every mutation path disabled, run a live dry-run covering authorized and
  unauthorized messages, each action, duplicate delivery, restart catch-up, invalid
  file, action/screen mismatch, and Slack receipt retry.
- [ ] Verify no listing, price observation, or sale state changed during dry-run.
- [ ] Run the full local check:

  ```bash
  ./scripts/check.sh
  git diff --check
  git status --short
  ```

- [ ] Confirm status contains no private screenshot, database, backup, secret, raw
  model output, or Slack payload.
- [ ] Commit: `docs: add Slack screenshot capture runbook`

## Task 12: Run the confirmation-required pilot

**External/local operational task:** do this only after Tasks 0 through 11 pass.

- [ ] Create an integrity-checked recovery backup before enabling confirmations.
- [ ] Keep both auto-commit flags false.
- [ ] Process controlled `sold` and `market` examples with owner confirmation.
- [ ] For each batch, independently compare screenshot, preview, Web UI state before,
  and Web UI state after.
- [ ] Exercise rejection, stale preview, duplicate delivery, worker restart, Slack
  receipt failure, and Web UI reopen correction.
- [ ] Record false positives, false negatives, model disagreement, review causes,
  timing, and cost separately by action without recording private row content.
- [ ] Confirm every committed capture has a backup, action-history rows, generic
  listing lineage, and exactly one receipt or pending receipt retry.
- [ ] Run SQLite integrity checks and focused Sales/capture tests after the pilot.
- [ ] Do not publish BigQuery automatically. If the owner chooses a manual snapshot,
  verify only generic lineage is present before upload.

**Exit condition:** confirmation mode is reliable and auditable. Operational pilot
results belong in the dated session note; no code commit is required unless a defect
is fixed in a separate atomic task.

## Task 13: Consider guarded autonomy separately for each action

**Conditional task:** do not schedule or implement this merely because confirmation
mode exists.

- [ ] For `sold`, demonstrate exact private-corpus performance and at least 20 live
  confirmed batches with zero false-positive mutations.
- [ ] Separately repeat the requirement for `market`.
- [ ] Require exact agreement between primary and independently prompted verification
  extractions for every proposed automatic batch.
- [ ] Add tests proving each auto-commit flag controls only its own action and every
  warning, mismatch, conflict, partial duplicate, or verification disagreement falls
  back to review.
- [ ] Enable at most one action flag at a time, monitor initial batches, and retain the
  immediate configuration rollback to confirmation mode.
- [ ] Record the action-specific approval decision in a new ADR or approved design
  amendment before changing the default.

## End-to-end acceptance checklist

- [ ] Gate 0 private examples exist and remain ignored.
- [ ] Only one allowlisted owner in one private channel can create actionable batches.
- [ ] Caption/button action is explicit and agrees with the extracted screen kind.
- [ ] Exact names, prices, counts, latest recipes, and approved professions are
  deterministic and tested.
- [ ] `sold` changes only exact active matches and snapshots cost at Slack time.
- [ ] `market` creates only missing exact active counts and linked append-only prices.
- [ ] Neither action invents catalog data, reprices, deletes, or infers absence.
- [ ] Every batch is idempotent, restart-safe, backed up, revalidated, and atomic.
- [ ] Slack receipt failure cannot repeat or roll back a committed mutation.
- [ ] Existing FastAPI manual and JSON behaviors pass regression tests.
- [ ] Capture-private data remains out of Git, public checks, snapshots, BigQuery, and
  dbt; only generic listing lineage is published.
- [ ] `./scripts/check.sh`, `git diff --check`, and the public-file policy pass.
- [ ] Confirmation mode remains the default until an action independently earns a
  documented autonomy decision.
