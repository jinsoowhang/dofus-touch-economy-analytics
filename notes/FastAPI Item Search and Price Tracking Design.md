# FastAPI Item Search and Price Tracking Design

**Status:** Approved

**Date:** 2026-08-20

## Objective

Build a single-user, local-first FastAPI website for searching Dofus Touch items,
viewing their recipes, recording observed market prices, and recalculating crafting
cost, profit, and ROI without losing price history.

The website adds an operational application boundary to the existing analytics
repository. SQLite owns transactional website state. DuckDB and dbt remain the
downstream analytical warehouse and transformation layer.

## Chosen approach

Use:

- FastAPI for web and JSON endpoints.
- Jinja templates and HTMX for server-rendered pages and inline updates.
- Synchronous SQLAlchemy 2.0 for persistence.
- Alembic for application-database migrations.
- SQLite for the ignored local application database.
- DuckDB and dbt for downstream analytics, not transactional website writes.

This is preferred over writing directly to DuckDB because website updates are
transactional operational data. A separate React frontend and PostgreSQL deployment
would add authentication, deployment, and API complexity before the core workflow is
validated.

## Scope

### Included

- Validate and import `item_cost.csv` and `item_recipes.csv` from ignored local paths.
- Search items by case-insensitive normalized name.
- View an item, its recipe, current prices, and price history.
- Record a timestamped price observation for any item or ingredient.
- Store market lot quantity and total price and derive unit price.
- Recalculate recipe cost, profit, and ROI after each observation.
- Invalidate an incorrect observation with a reason while preserving the audit trail.
- Expose versioned JSON endpoints that reuse the same application services as the
  HTML routes.
- Run locally on the loopback interface without accounts.

### Deferred

- `item_sales.csv` ingestion until its dates and row grain are deterministic.
- Public hosting, authentication, authorization, and multiple users.
- React or another separate frontend.
- Editing item identity, aliases, or recipe structure through the website.
- Automatic fuzzy merging of source names.
- Market fees, taxes, alerts, dashboards, scraping, or game-client automation.
- The SQLite-to-DuckDB analytical ingestion and dbt models. The application schema
  preserves identifiers, timestamps, and provenance needed for that next milestone.

## System boundaries

```text
ignored item_cost.csv + item_recipes.csv
                    |
                    v
           validation and import
                    |
                    v
       ignored SQLite application DB
          |                       |
          v                       v
 FastAPI HTML and JSON      later DuckDB ingestion
          |                       |
          v                       v
    Jinja + HTMX              dbt analytics
```

Raw CSV files remain immutable and ignored. The importer reads them but never rewrites
them. The SQLite database is also ignored and is changed only through migrations,
imports, or application services. DuckDB remains isolated from request-time writes.

Implementation must add an ADR documenting SQLite as the operational database and
the boundary between operational and analytical state.

## Package structure

Application code will live under one installable package in `src/`:

```text
src/dofus_touch_economy/
  app.py
  config.py
  database.py
  models.py
  schemas.py
  importers/
  repositories/
  services/
  routers/
    web.py
    api.py
  templates/
  static/
```

- Routers translate HTTP requests and responses only.
- Services own import, pricing, invalidation, and calculation rules.
- Repositories own SQLAlchemy queries and transactions.
- Models describe persisted application state.
- Schemas validate commands and JSON representations.

The initial modules should remain small; they should be split further only when one
file develops multiple independent responsibilities.

## Application database

The default local database path is `data/app/dofus_touch.sqlite3`. The directory and
database files must be ignored, with a tracked README documenting their purpose.
The application uses one configured market context per process. The setting defaults
to `unspecified`, is displayed in the UI, and is stored on every new observation. A
different server or market uses a separate configured value rather than silently
mixing observations in one current-price calculation.

### `import_batches`

Records each source import:

- stable identifier
- dataset name
- source filename
- SHA-256 checksum
- started and completed timestamps
- accepted, rejected, and warning counts
- final status

An already successful dataset/checksum pair is a no-op, making imports idempotent.

### `source_records`

Preserves each imported row for local reconciliation:

- import-batch identifier
- dataset and one-based source row number
- raw row payload serialized without silent repair
- accepted or rejected status
- validation messages

This local ignored table preserves source price, cost, profit, ROI, and spreadsheet
error values even when those fields are not promoted into operational application
state.

### `items`

Represents a canonical searchable item:

- stable UUID exposed to routes and future analytics
- display name
- normalized name
- optional category
- created and updated timestamps

Normalization trims surrounding whitespace, collapses repeated internal whitespace,
and applies Unicode case folding. It does not perform fuzzy correction.

### `source_item_names`

Preserves source identity and matching decisions:

- dataset and source-row locator
- source field or ingredient position
- raw item name
- normalized item name
- resolved item UUID when unambiguous
- resolution status

An exact normalized name maps automatically only when it has one candidate. Multiple
candidates remain unresolved and generate an import conflict. Search may use partial
matching, but partial or fuzzy matching never establishes identity.

### `recipes`

Stores:

- stable recipe identifier
- crafted item UUID
- profession
- source-row locator
- created and updated timestamps

### `recipe_ingredients`

Stores one row per populated source ingredient group:

- recipe identifier
- one-based source position
- ingredient item UUID when resolved
- raw ingredient name for reconciliation and unresolved display
- required quantity

The combination of recipe and source position is unique. An unresolved ingredient is
shown explicitly and makes calculated recipe cost incomplete.

### `price_observations`

Stores append-only manual observations:

- monotonically increasing internal identifier used only for deterministic ordering
- stable observation UUID
- item UUID
- positive integer `lot_quantity`
- positive whole-kama `total_price`
- timezone-aware `observed_at`
- `recorded_at`
- `market_context`
- optional note
- source fixed to `manual` in this milestone
- optional `invalidated_at` and required invalidation reason

Unit price is derived from total price divided by lot quantity. It is not the source
of truth. Calculation code uses decimal arithmetic so a lot can produce a fractional
per-unit value without floating-point drift.

The existing `item_cost.price` values lack deterministic observation timestamps. The
importer preserves them in import provenance and reconciliation output, but it does
not silently convert them into current price observations.

## Import behavior

The import command accepts the canonical ignored paths and performs these steps:

1. Verify encoding, headers, and source checksum.
2. Preserve source-row locators and raw item names.
3. Parse only fields required for catalog and recipe behavior.
4. Normalize names using the documented deterministic rule.
5. Reuse exact unambiguous items and create category-aware candidates when needed.
6. Expand populated recipe ingredient groups into ordered ingredient rows.
7. Record rejected rows, warnings, and ambiguous matches in a report.
8. Commit accepted application rows and the import-batch result in one transaction.

File-level contract failures abort without database changes. Row-level failures are
reported and excluded while valid rows load transactionally. The command exits
nonzero when rows are rejected so incomplete imports are visible even though accepted
rows remain usable.

The importer never guesses dates, repairs names fuzzily, selects one duplicate price
silently, or treats spreadsheet error strings as numbers.

## Price selection and calculations

The current price for an item is its latest valid observation ordered by:

1. `observed_at` descending
2. `recorded_at` descending
3. internal observation identifier descending as a deterministic final tie-breaker

The lookup is restricted to the application's active market context. Invalidated
observations never participate in current-price or recipe calculations.

Calculations are:

```text
unit_price = total_price / lot_quantity
ingredient_cost = required_quantity * current_ingredient_unit_price
recipe_cost = sum(ingredient_cost)
profit = current_crafted_item_unit_price - recipe_cost
roi = profit / recipe_cost
```

Recipe cost is incomplete when any ingredient is unresolved or lacks a valid current
price. Profit and ROI are shown only when recipe cost is complete and the crafted item
has a current price. Missing values are never treated as zero. ROI is undefined when
recipe cost is zero.

Source-derived cost, profit, difference, and ROI fields remain reconciliation data;
the application recomputes governed values from observations and recipe quantities.

## Web experience

### Item search

`GET /items?q=<query>` returns a responsive search page. Matching is case-insensitive
substring search over normalized names, with category displayed to distinguish
duplicates. The current dataset size does not justify SQLite FTS in this milestone.

### Item detail

`GET /items/{item_uuid}` displays:

- name and category
- latest valid price and its observation time
- recipe and profession when available
- each ingredient, quantity, current unit price, and extended cost
- incomplete-price and unresolved-match indicators
- recipe cost, profit, and ROI when calculable
- recent price history

### Recording a price

Each crafted item and resolved ingredient has an inline form for lot quantity, total
price, observation time, the displayed active market context, and an optional note.
The context comes from application configuration rather than arbitrary per-form text.
Observation time defaults to the current time but remains explicit and editable. A
successful HTMX request replaces the relevant price, calculation, and history
fragments.

### Invalidating a price

An observation may be invalidated once with a required reason. The service records
the invalidation atomically and recalculates current price. Direct edit and hard delete
operations are not exposed.

HTMX must be pinned and stored with documented provenance so the local application
does not depend on a live CDN.

## HTTP interfaces

HTML routes:

- `GET /` redirects to `/items`.
- `GET /items` searches and lists items.
- `GET /items/{item_uuid}` renders item detail.
- `POST /items/{item_uuid}/price-observations` records an observation.
- `POST /price-observations/{observation_uuid}/invalidation` invalidates one.

JSON routes under `/api/v1` expose equivalent search, detail, create-observation, and
invalidate-observation behavior. HTML and JSON routers call the same services rather
than duplicating business rules.

## Validation and error handling

- Unknown items and observations return `404`.
- Nonpositive quantities or prices and malformed timestamps return `422`.
- Invalidating an already invalid observation returns `409`.
- Import schema failures return a nonzero CLI result and a readable validation report.
- SQLite command operations run in explicit transactions and roll back on failure.
- HTML errors render next to the relevant form; JSON errors use stable structured
  details.
- Unexpected failures are logged with request context but without raw CSV contents or
  secret values.

## Local security boundary

- The documented launch command binds to `127.0.0.1` by default.
- Allowed hosts are limited to loopback names in local configuration.
- CORS is not enabled.
- Browser mutation requests must be same-origin.
- Jinja autoescaping remains enabled.
- All SQL uses SQLAlchemy parameters rather than interpolated user input.
- The SQLite file, local configuration, raw files, and generated reports remain
  ignored.

Binding to a non-loopback interface is outside this design. Public deployment first
requires authentication, authorization, CSRF protection appropriate to the deployment,
managed secrets, HTTPS, and a production database decision.

## Testing strategy

### Unit tests

- name normalization
- latest-valid-price ordering
- decimal unit-price calculation
- recipe cost, profit, and ROI
- missing-price and unresolved-ingredient behavior
- observation invalidation rules

### Persistence tests

- migrations against a temporary SQLite database
- repository transactions and rollback
- import idempotency by dataset checksum
- exact matching and ambiguity reporting
- source-row and raw-name provenance

### HTTP tests

- search and item-detail responses
- valid and invalid price submissions
- immediate recalculation after a new observation
- invalidation and fallback to the previous valid price
- matching HTML and JSON behavior through shared services
- loopback/same-origin mutation protections

Only synthetic fixtures are committed. CI never requires the private CSVs or local
SQLite/DuckDB files. Existing Ruff, Pytest, dbt, SQLFluff, pre-commit, and public-file
checks remain part of the full verification script.

## Documentation changes required during implementation

- Add an ADR for SQLite operational state and DuckDB analytical state.
- Update the architecture diagram and repository map.
- Document database migration, import, and launch commands.
- Add the application database and import reports to ignore/public-file policies.
- Update `MEMORY.md` and dated session notes with stable decisions and verified results.

## Success criteria

The milestone is complete when a contributor can:

1. Install the locked environment and migrate an empty local application database.
2. Import the local cost and recipe exports with a deterministic validation report.
3. Search for an imported item in the browser.
4. View its recipe and clearly see missing or unresolved inputs.
5. Record lot-based item and ingredient prices.
6. See current prices, recipe cost, profit, and ROI update correctly.
7. Invalidate an incorrect observation and recover the previous valid price.
8. Exercise equivalent versioned JSON endpoints.
9. Run all tests and repository checks without access to private source data.
