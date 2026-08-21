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
