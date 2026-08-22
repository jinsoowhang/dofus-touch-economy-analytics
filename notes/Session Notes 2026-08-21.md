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

## Follow-up: Sales Tracking

### Context

Simplified Item Search price entry and added an operational Sales page for active and
completed listings. The user requested faster iterations, so no broad README or design
documents were changed.

### Work Completed

- Removed lot quantity from Item Search price entry and catalog display; HTML price
  records now use implicit quantity one.
- Redirected successful price recording to Item Search with a confirmation notice.
- Added a Sales tab with direct item selection, lot quantity, automatic selling start
  time, active listings, a Mark sold action, and sold history with `date_sold`.
- Linked price observations to automatically created Sales entries and display their
  recorded total price on the Sales page.
- Added migration `0003`, which seeded manual price observations recorded that day as
  active listings without duplicating their linked observation.

### Decisions

- Each price observation represents a separate sale entry with its recorded lot
  quantity; the Item Search workflow therefore creates quantity-one entries.
- Direct Sales entries may use any positive lot quantity and have no required price.
- Selling and sold timestamps are recorded automatically in UTC.
- Broad documentation updates are reserved for meaningful public contract changes or
  explicit requests; required memory and session records remain part of session close.

### Verification

- `./scripts/check.sh` passed with 120 Python tests plus application compilation, dbt
  debug and parse, SQLFluff, and public-file verification.
- Focused Sales, web, model, and populated migration tests passed.
- Migration `0003` upgraded the local database and seeded all 15 manual prices recorded
  on 2026-08-21 as active Sales listings.
- The running loopback site returned `/sales` with HTTP 200, 15 active entries, linked
  prices, and Mark sold controls.

### Next Step

Merge and push the feature branch only after approval. Future Sales enhancements can
add optional direct-entry pricing or reporting when requested.

## Follow-up: Compact Item Display and Editable Sales

- Replaced the Item Search success banner with a fixed corner notification containing
  the updated item name; it fades after three seconds.
- Displayed category labels in title case without rewriting source values, removed the
  currency suffix from catalog prices, and reduced visible dates to `YYYY-MM-DD`.
- Added an independent editable asking price to Sales, backfilled it from linked price
  observations, and added Duplicate and inline Update price actions.
- A duplicate copies item, lot quantity, and asking price into a separate active
  listing, so its price can change without affecting the original.
- Migration `0004` completed with no missing linked prices. `./scripts/check.sh` passed
  with 126 tests, and live Item Search and Sales smoke requests returned HTTP 200.

## Follow-up: Item Icons

- Added a local item-icon cache sourced by exact name from the current Dofus Touch
  client, DofusDB, and Dofus Wiki, with reviewed aliases for legacy source spellings.
- Displayed icons throughout Item Search, item detail and recipes, and Sales.
- Cached valid PNGs for all 997 local catalog items with no missing or failed downloads.
- Migration `0005` records icon provenance; cached binaries remain ignored local data.
- `./scripts/check.sh` passed with 133 tests, and live Item Search and Sales requests
  returned HTTP 200 with their icon routes serving PNG files.

## Follow-up: Seed Current Prices from Raw Costs

- Superseded the earlier provenance-only decision for `item_cost.csv`: each new file
  checksum now seeds idempotent, lot-one current-price observations.
- The last file occurrence wins for 37 duplicate identity groups; raw source rows remain
  preserved, and cost imports do not create Sales listings.
- Applied 984 unique raw prices to the live database. Together with 13 retained manual
  prices, all 997 catalog items now have a current price; Sales remains at 19 listings.
- `./scripts/check.sh` passed with 135 tests, and live duplicate examples displayed the
  expected final-file prices with HTTP 200.

## Follow-up: Sortable Item Search

- Made Item Name, Category, Current Price, and Last Observed headers clickable, with a
  visible ascending or descending arrow on the active field.
- Repeated clicks toggle direction, active search text and sorting are preserved, and
  missing values remain at the bottom in both directions.
- `./scripts/check.sh` passed with 140 tests; live price-descending order and indicators
  returned correctly with HTTP 200.

## Follow-up: Sales Row Management and Sorting

- Removed lot quantity from Sales entry and both Sales tables; new and duplicated rows
  use one-item semantics.
- Added an X action to active and sold rows with browser confirmation before deletion;
  deleting a linked Sales row preserves its price observation.
- Made every displayed data header sortable in both Sales tables, with independent
  ascending/descending arrows and retained sorting for the other table.
- `./scripts/check.sh` passed with 151 tests. A read-only live check confirmed all 26
  existing active rows remained intact, sorted prices correctly, and exposed confirmed
  delete controls without showing lot quantity.

## Follow-up: Sales Prices Update Item History

- A price entered when adding or repricing a Sales row now appends a linked quantity-one
  price observation, updates the item's current price, and preserves older observations.
- Duplicate alone does not create redundant history, and an unpriced Sales row still
  creates no observation.
- Corrected the existing Clay-headed Giant's Helmet listing to current price 98,000
  while retaining 100,000 in history, and captured Coco Blop Belt at 38,000 after it
  was submitted during the server restart.
- `./scripts/check.sh` passed with 153 tests; the live item pages showed the expected
  current prices and history.

## Follow-up: Sales Filtering, Trends, and Full Catalog

- Added an optional Category filter above the Sales item selector; it narrows the item
  choices in the browser without changing the submitted listing data.
- Preserved both Sales table sort selections after add, duplicate, reprice, sell, and
  delete actions.
- Displayed Sales dates in `America/Los_Angeles` time and added a daily sold-price line
  chart with total revenue, item count, average priced sale, and accessible daily totals.
- Added an idempotent live-client catalog sync and imported every unique exchangeable
  item/category identity while preserving existing UUIDs, prices, sales, and history.
- The live database now contains 11,400 items across 183 local category labels and
  11,390 cached icons. Ten official catalog entries have unavailable Ankama PNG URLs
  and intentionally retain the existing missing-image state instead of incorrect art.
- Saved a pre-sync local database backup at
  `data/app/verification-before-touch-catalog-20260821.sqlite3`.
- The full check passed with 158 tests, dbt validation, SQLFluff, and public-file policy;
  live Item Search, item icons, Sales filtering, sorting state, Pacific dates, and the
  chart all returned successfully.

## Follow-up: Compact Sales Editing and Collapsible Sections

- Capitalized manual item names only at space boundaries, corrected the existing
  `Daggero's Red Necklace` row, and title-cased visible field and section labels.
- Made page sections collapsible, required Sale Price for new listings, moved typed
  item matches to the top of the Sales dropdown, and saved inline price edits on Enter
  or blur without an Update button.
- The full check passed with 160 tests; live smoke checks confirmed the new markup and
  scripts, and a missing-price request left all 79 Sales rows unchanged.

## Follow-up: Sales Recovery, Item Categories, and Price Formatting

- Added a ↩ Sold History action that returns the same row to Currently Selling by
  clearing only `date_sold`, while preserving its price, dates, UUID, history, and sort state.
- Added an optional Item Search Category filter that combines with the name query and
  persists through live filtering and column sorting.
- Displayed prices with comma grouping and accepted correctly grouped comma-formatted
  values in Item Search and Sales price inputs.
- The full check passed with 163 tests; live read-only checks confirmed all three
  features while counts remained at 79 Sales rows and 1,038 price observations.

## Follow-up: Complete Live Recipe Catalog

- Added an idempotent command that validates and imports the live English Dofus Touch
  recipe graph from Ankama with source-record and item-name provenance.
- Required every crafted item and ingredient to resolve to the local catalog before
  committing the batch; the sync appends recipe versions and does not replace prices,
  Sales listings, catalog rows, or earlier CSV recipes.
- Imported all 4,306 recipes for exchangeable craftable items with 19,333 fully linked
  ingredient rows. A repeated sync created no additional database rows.
- Confirmed the live Abyss Necklace page shows the Jeweller recipe with all eight
  ingredient icons and quantities from the official source.
- The full check passed with 165 tests, application compilation, dbt validation,
  SQLFluff, and public-file policy.

## Follow-up: Recipe Ingredient Costs

- Replaced each separate Recipe "View item" action with a highlighted ingredient-name
  link and added comma-formatted Per Unit Price and Total Cost columns.
- Kept missing prices explicit instead of substituting Ankama's static item values,
  which are not server-specific player-market prices.
- Research found TouchEmu's current third-party Touch Market, but no documented public
  API or export suitable for safe ingestion; older community trackers were stale or
  access-restricted.
- The full check passed with 166 tests, and the live Abyss Necklace page displayed
  correct linked names, priced totals, and missing-price placeholders.

## Follow-up: Active Sales Total and Recipe Price Editing

- Added the exact summed asking price beside the Currently Selling active-item count.
- Replaced Duplicate and Mark Sold text buttons with compact overlapping-page and
  checkmark icons while retaining descriptive labels and tooltips for accessibility.
- Made resolved Recipe per-unit prices editable on Enter or blur, including blank
  missing-price fields and comma-formatted values.
- Recipe edits append price history, create the ingredient's active Sales row under the
  existing manual-price rule, recalculate ingredient totals, and return to the Recipe
  section with a notification; unrelated item UUIDs are rejected.
- The full check passed with 168 tests. A read-only live smoke matched 117 active rows
  to a total price of 6,436,350 and rendered eight editable Abyss Necklace ingredients.

## Follow-up: Compact Item Price and Crafting Metrics

- Replaced the Item detail timestamp, note, and total-price form with one inline
  Current Price field that saves on Enter or blur and preserves read-only history.
- Removed all Item detail invalidation controls from the browser interface.
- Redesigned Crafting Metrics as responsive Recipe Cost, Profit, and percentage ROI
  cards, with a distinct status panel for incomplete recipe costs.
- The full check passed with 169 tests; a read-only live smoke confirmed the legacy
  fields are absent and a fully priced recipe renders all three metric cards.

## Follow-up: Sales Cost and Profit

- Added sortable, read-only Cost and Profit columns to Currently Selling and Sold
  History. Cost uses the latest recipe and current ingredient prices; Profit subtracts
  that cost from the row price, while incomplete costs remain explicit.
- Expanded Sales Over Time into distinct Sales, Cost, and Profit series with negative
  profit support, summary totals, cost coverage, and accessible daily values.
- The full check passed with 170 tests. A live read-only smoke rendered the new columns
  and correctly reported missing cost coverage without modifying Sales data.
