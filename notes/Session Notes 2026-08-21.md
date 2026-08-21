# Session Notes 2026-08-21

## Context

Completed and verified the approved local FastAPI item-search and price-tracking milestone in the isolated feature worktree.

## Work Completed

- Fixed SQLite portability for reserved filename characters and shared threaded in-memory tests.
- Added the seven-table SQLAlchemy operational schema and initial reversible Alembic migration.
- Added deterministic item-name normalization and decimal lot-price, recipe-cost, profit, and ROI calculations.
- Added strict cost and recipe CSV validation with invented public fixtures.
- Added transactional, checksum-idempotent catalog and recipe import with raw-row provenance, explicit rejection records, and ambiguity reporting.
- Added catalog and price repositories, application services, validated commands, response schemas, and atomic observation invalidation.
- Added loopback-only FastAPI HTML and `/api/v1` JSON routes with trusted hosts and same-origin browser mutations.
- Added Jinja and vendored HTMX browser flows for search, detail, price recording, recalculation, and invalidation.
- Added responsive local styling, reviewed HTMX assets and license, import and web entry points, ADR 0002, and developer documentation.
- Closed final review findings by adding structured rejection details to reports, normalizing persisted observations to UTC, and selecting the latest imported recipe version.

## Durable Decisions

- SQLite owns mutable operational application state; DuckDB and dbt remain separate downstream analytical state.
- Price observations are append-only lot totals. Incorrect observations are invalidated once with a reason and remain auditable.
- Current price selection is restricted to the configured market context and ordered by observation time, recording time, then internal identifier.
- Imported cost prices remain reconciliation provenance and never become timestamped current market observations.
- Exact normalized names resolve automatically only when unambiguous. Ambiguous recipe ingredients remain unresolved.
- `item_cost.csv` and `item_recipes.csv` are in application-import scope. `item_sales.csv` remains deferred.

## Verification

- `uv sync --locked --all-groups` completed successfully.
- `./scripts/check.sh` passed with 80 Python tests, application compilation, dbt debug and parse, SQLFluff, and public-file verification.
- `DO_NOT_TRACK=1 uv run pre-commit run --all-files` passed all configured hooks, including application compilation.
- The pinned HTMX JavaScript and license matched their approved SHA-256 digests.
- A disposable ignored SQLite database migrated from empty to Alembic head.
- Local import created two batches with 1,271 accepted rows, 47 rejected rows, and no ambiguity warnings.
- The ignored JSON report contained one structured entry per rejected row with dataset, row number, and validation messages, without printing raw rows to the console.
- The accepted rows comprised 1,022 cost rows and 249 recipe rows. All 47 rejected recipe rows lacked both required recipe identity fields, matching the approved contract and known source shape.
- The application importer read only the cost and recipe inputs; sales remained outside the command interface.
- A server bound only to `127.0.0.1` returned HTTP 200 for `/items` and shut down cleanly.
- The verification database, report, and private CSVs were ignored. The only tracked CSVs were the two invented fixtures.
- dbt emitted the expected warning for the three empty model-layer configuration paths because analytical models remain deferred.
- Pytest emitted a non-blocking upstream TestClient deprecation warning concerning the pinned HTTPX integration.

## Next Step

Review the complete feature range, resolve any Critical or Important findings, then merge and push only after approval. The next product milestone is immutable SQLite-to-DuckDB ingestion followed by dbt models for operational price analytics; sales remain blocked on deterministic dates and grain.

## Follow-up: Missing Catalog Items

### Context

Added a safe local workflow for items that are absent from the imported catalog so a
price can be recorded without waiting for a new CSV export.

### Work Completed

- Added item creation provenance and a populated-database Alembic migration.
- Added validated manual catalog creation with normalized duplicate protection.
- Added advisory close-name suggestions that never establish or merge identity.
- Added no-result HTML creation, a versioned JSON creation endpoint, and source display
  on item detail.
- Added import reconciliation that enriches a sole uncategorized manual item without
  changing its UUID, provenance, recipes, or price history.
- Updated the architecture, data contract, application design, and README.
- Replaced a SQLite batch-table migration after populated verification exposed a
  foreign-key conflict; the regression test now upgrades a database containing a
  dependent price observation.

### Decisions

- Manual creation accepts an exact display name and optional category.
- If category is omitted, any exact normalized-name candidate blocks creation. If a
  category is supplied, the normalized name/category pair remains the identity key.
- Similar-name scoring is UI guidance only and never changes source resolution rules.
- `created_source` records how an item first entered the catalog and remains `manual`
  when a later import confirms or enriches it.

### Verification

- `./scripts/check.sh` passed with 93 Python tests, application compilation, dbt debug
  and parse, SQLFluff, and public-file verification.
- `DO_NOT_TRACK=1 uv run pre-commit run --all-files` passed every configured hook.
- A populated local database upgraded from revision `0001` to `0002`, retaining 984
  catalog items and its existing observation; all existing items received imported
  creation provenance.
- A disposable loopback HTTP smoke returned the no-result creation form, created a
  manual item with `201`, found it through search, rendered its detail with manual
  provenance, and immediately recorded a lot price with the expected unit price.
- The upstream TestClient deprecation warning and the three expected empty dbt model
  configuration warnings remain non-blocking.

### Next Step

Merge and push the feature branch only after approval. The next product milestone
remains immutable SQLite-to-DuckDB ingestion and dbt models for operational price
analytics; sales ingestion still requires deterministic dates and confirmed grain.

## Follow-up: Automatic Category Recognition

### Context

Improved manual item creation so lowercase item names are presented consistently and
common equipment categories do not need to be entered by hand.

### Work Completed

- Added whitespace normalization and title casing for manual item names and entered
  category overrides.
- Added a conservative final-word suffix map for common equipment categories.
- Added browser previews for the formatted name and recognized category.
- Applied the same behavior through the HTML and versioned JSON creation interfaces.
- Added focused normalization, service, API, and browser regression tests.
- Updated the README, data contract, and application design.

### Decisions

- Category inference matches only a complete final word from the reviewed suffix map;
  embedded substrings do not classify an item.
- An explicit category override takes precedence over inferred category.
- Inference remains a manual-creation convenience and does not change imported source
  values or fuzzy identity-resolution rules.
- Python title casing is the requested display rule for new manual items; existing
  imported and manually created records are not rewritten.

### Verification

- `./scripts/check.sh` passed with 103 Python tests, application compilation, dbt debug
  and parse, SQLFluff, and public-file verification.
- `DO_NOT_TRACK=1 uv run pre-commit run --all-files` passed every configured hook.
- A disposable loopback HTTP smoke previewed `Chouquish Belt` and category `Belt` from
  the lowercase input and persisted both values with `201 Created`.
- The upstream TestClient deprecation warning and the three expected empty dbt model
  configuration warnings remain non-blocking.

### Next Step

Merge and push the feature branch only after approval. Extend the reviewed suffix map
only when another unambiguous equipment type is needed; do not infer arbitrary source
categories.

## Follow-up: Catalog Table and Navigation

### Context

Expanded Item Search into the first tab of a multi-page navigation and made the full
catalog browsable without requiring an initial query.

### Work Completed

- Added a shared top-level navigation with Item Search marked as the active tab.
- Changed blank item search to return the complete catalog in alphabetical order.
- Added bulk current-price selection for catalog summaries using one ranked query per
  market context instead of one database query per item.
- Replaced the result list with a responsive table showing item name, category, current
  unit price, observed lot, observation time, and an update-price action.
- Made every table cell link to item detail, where price changes remain append-only
  observations with history and invalidation support.
- Preserved delayed HTMX name filtering and missing-item creation when no row matches.
- Updated the README, architecture, application design, and focused regression tests.

### Decisions

- Item Search is the first reusable top-level tab; later pages should extend the shared
  navigation rather than add page-local menus.
- The HTML catalog is intentionally uncapped for the current local dataset, while the
  JSON search endpoint retains its existing result limit.
- The table displays the latest valid price only for the configured active market.
- “Update price” opens detail and records a new observation; existing observations are
  never edited in place.

### Verification

- `./scripts/check.sh` passed with 111 Python tests, application compilation, dbt debug
  and parse, SQLFluff, and public-file verification.
- `DO_NOT_TRACK=1 uv run pre-commit run --all-files` passed every configured hook.
- A live loopback smoke rendered all 989 local catalog items in alphabetical table
  rows, including seven current prices, in approximately 0.11 seconds.
- A name query reduced the live table to eight matching rows, and a selected row opened
  item detail with HTTP 200.
- Every rendered item row contained links across all six table columns.
- The upstream TestClient deprecation warning and the three expected empty dbt model
  configuration warnings remain non-blocking.

### Next Step

Merge and push the feature branch only after approval. Add future application pages as
new shared-header tabs while retaining Item Search as the catalog and price-entry hub.
