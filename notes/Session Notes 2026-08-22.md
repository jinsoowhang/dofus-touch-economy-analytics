# Session Notes 2026-08-22

## Context

Prepared the repository and account-side procedure for a BigQuery and free dbt
Developer hosted pilot. The user already has Google BigQuery and dbt accounts, but
the active environment has no authenticated Google Cloud CLI or external account
connector.

## Work Completed

- Confirmed from current official dbt documentation that free Developer accounts use
  service-account JSON authentication for BigQuery; BigQuery OAuth and workload
  identity federation require Enterprise-tier plans.
- Confirmed dbt's documented baseline roles are BigQuery Data Editor and BigQuery
  User, and chose a dedicated Google Cloud project to contain those project-level
  grants.
- Added a reproducible BigQuery, service-account, dbt connection, GitHub,
  environment, verification, and cost-control guide.
- Accepted an ADR for a hosted pilot that retains local dbt Core and DuckDB until
  model parity is demonstrated.
- Added `.secrets/` to Git ignore rules and the public-file policy, with a regression
  test for a BigQuery service-account key path.
- Updated the architecture, README, agent instructions, and memory.
- Mechanically formatted pre-existing Python snippets in the FastAPI implementation
  plan so the repository's full check could pass; this was committed separately from
  the hosted-pilot change.

## Decisions

- Use `dofus_dev` and `dofus_prod` as the BigQuery base datasets.
- Use dbt's Core `Latest` release track during the pilot rather than hosted BigQuery
  Fusion while Fusion support remains preview.
- Cap individual dbt queries at 1 GB processed and recommend a small BigQuery daily
  query quota.
- Use one single-purpose service account for development and deployment during the
  solo pilot, then separate identities before multi-user or production-sensitive
  use.
- Do not add placeholder dbt models or schedule a deployment job before deterministic
  ingestion and real models exist.
- Keep private raw exports local until a secure loader implements the approved source
  contract, metadata, and rejection behavior.

## Verification

- `uv run pytest tests/python/test_check_public_files.py -v` passed after the new
  `.secrets/` policy was implemented.
- `git diff --check` passed.
- `./scripts/check.sh` passed after synchronization, including Ruff lint and
  formatting, 172 Python tests, application compilation, dbt debug and parse against
  local DuckDB, SQLFluff, and the public-file policy.
- GitHub authentication and the public repository URL were verified read-only.
- Hosted BigQuery connection, parse, and compile verification remain pending because
  account credentials are intentionally not available to this environment.

## Next Step

Use `docs/dbt-cloud-bigquery-setup.md` with the user's Google Cloud project ID and
dataset location, then confirm the dbt connection test plus hosted `dbt parse` and
`dbt compile`.

## GitHub Synchronization

- The first push was rejected safely because `origin/main` had advanced.
- Fetched `origin/main` from the previously observed `2e6e06c` tip to `171ee1d`.
- Created rollback branch `backup-pre-origin-sync-20260822` at the pre-sync local tip.
- Reviewed the 64 incoming commits and their 87-file delta before applying changes.
- Replayed only the hosted-pilot commit onto the fetched remote tip. The local
  formatting commit was dropped because remote commit `8686785` already contained
  the same mechanical formatting.
- Resolved conflicts in `AGENTS.md`, `MEMORY.md`, `README.md`,
  `docs/architecture.md`, and `scripts/check_public_files.py` by preserving the
  completed FastAPI implementation and layering the hosted pilot onto it.
- Preserved SQLite as ADR 0002 and assigned the BigQuery pilot ADR 0003.
- The replayed hosted-pilot commit is `9a6caa5`.

## Operational BigQuery Ingestion

### Work Completed

- Located the latest normalized operational SQLite state in an ignored stale
  worktree and copied it through SQLite's backup API to the canonical ignored
  `data/app/dofus_touch.sqlite3` path without modifying the source database.
- Added an exact-schema snapshot extractor for import batches, source records, items,
  source-name resolutions, recipes, recipe ingredients, price observations, and
  application Sales listings.
- Added a BigQuery loader that content-addresses snapshots, creates partitioned and
  clustered raw tables, makes partial retries safe, and publishes the manifest last.
- Added BigQuery-backed dbt sources, nine staging models, two intermediate models,
  four marts, generic schema tests, and three domain invariant tests.
- Added an operator guide with local dry run, ADC authentication, upload commands,
  Google Cloud sidebar verification, dbt Studio build steps, and cost-control notes.
- Accepted ADR 0004 and updated the public architecture, data contract, setup guide,
  README, agent guidance, and memory.

### Decisions

- Load normalized operational SQLite state instead of manually uploading raw CSVs.
- Continue excluding ambiguous `item_sales.csv`; application `sale_listings` are the
  only hosted Sales source because they have stable IDs and deterministic timestamps.
- Load `dofus_dev` and `dofus_prod` by default so each dbt environment has an
  identical immutable source snapshot.
- Authenticate the local loader with user Application Default Credentials. Do not
  create or download another service-account key; dbt Cloud keeps its existing key.
- Keep production dbt execution manual until development builds and costs are
  verified repeatedly.

### Verification

- The canonical database dry run produced snapshot
  `afc1d6b429721529f3468ae8f395f0541cc817c71f54e75537a58512af3113ea`, schema
  version `0005`, and 67,266 normalized rows across the eight contracted tables.
- Five focused extractor and loader tests passed, including hash stability, schema
  drift rejection, no-credential dry run, manifest-last publication, and idempotent
  reruns.
- `dbt parse`, `dbt compile`, and SQLFluff passed for 15 models, 81 data tests, and
  nine sources.
- The first full check exposed and then received a fix for the documented entry-point
  expectation. The final `./scripts/check.sh` passed: Ruff lint and formatting, 177
  Python tests, package compilation, dbt debug and parse, SQLFluff, and the
  public-file policy.
- The actual BigQuery command stopped before changes because Google Application
  Default Credentials were unavailable. WSL has neither `gcloud` nor an existing ADC
  credential.

### Cloud Completion

- Installed the official Linux x86_64 Google Cloud CLI 581.0.0 under the WSL user
  directory after verifying Google's published SHA-256 checksum. The installation
  did not modify the repository or shell configuration.
- Completed browser-based user ADC authentication without putting a verification
  code or credential in chat, then assigned `claude-projects-489306` as the ADC quota
  project.
- Loaded snapshot
  `afc1d6b429721529f3468ae8f395f0541cc817c71f54e75537a58512af3113ea`
  into both `dofus_dev` and `dofus_prod`. Each manifest reports 67,266 source rows.
- Queried both datasets to verify `US` location, one manifest row, and exact per-table
  counts. An immediate loader rerun reported `already-loaded` for both datasets.
- The first guarded BigQuery `dbt build` exposed that BigQuery rejects parameterized
  decimal types inside `CAST`. Added an adapter-dispatched whole-amount division macro
  that retains `decimal(38, 9)` on DuckDB and uses unparameterized `numeric` on
  BigQuery.
- Reran the guarded BigQuery development build with dbt Core 1.12.0 and
  dbt-bigquery 1.12.0. All 15 models and 81 tests passed: 96/96 nodes, with no warnings,
  errors, or skips.
- Queried the development marts after the green build: 11,400 item rows, 1,138
  price-observation rows, 181 Sales rows, and 18,943 latest-recipe ingredient rows.
- Ran one guarded production build after the development result and cost check. All
  96 production nodes passed with no warnings, errors, or skips, and production mart
  counts exactly match development.
- The complete session used 4,660 MiB of billed query bytes across 306 recent query
  jobs, below the 0.01 TiB daily project quota. All raw and mart tables together use
  about 42.01 MiB of logical storage. The $10 budget remains alert-only, and no
  recurring job was scheduled.

### Next Step

Refresh dbt Studio so it sees the pushed model commit, run `dbt build` there to verify
the dbt Cloud execution path, then create a manual production deployment job only
after reviewing development lineage and costs.

## Public Project Description Refresh

### Work Completed

- Updated the public README to describe the implemented FastAPI, SQLite, BigQuery,
  and dbt architecture instead of an incomplete hosted pilot.
- Documented the exact manual snapshot command and clarified that website writes do
  not automatically update BigQuery or dbt models.
- Updated the GitHub profile project's Current Projects description to call this an
  economy tracker and analytics platform and to list the current primary stack.

### Verification

- Confirmed both repositories were clean before editing.
- `./scripts/check.sh` passed, including Ruff, 177 Python tests, package compilation,
  dbt debug and parse, SQLFluff, and the public-file policy.
- `git diff --check` passed in both repositories, and the profile entry appears
  exactly once in second position after `skills`.

## Local Item Icon Cache Recovery

### Cause and Repair

- The canonical SQLite database contained `icon_source_url` metadata for 11,390
  items, but the ignored `data/app/item_icons/` directory was absent. The UI therefore
  rendered local icon routes whose files returned 404.
- Ran `uv run dofus-fetch-icons --workers=8` to reconstruct the cache from the
  configured public sources. It restored 11,390 valid PNG files totaling 93 MB.
- Ten catalog entries have no downloadable upstream image and remain intentionally
  without an icon.
- Added the recovery command to the README because the cache is independent of the
  SQLite database and is not transferred with it.

### Verification

- Confirmed a cached file begins with the PNG signature.
- Confirmed the running FastAPI application serves a cached icon with HTTP 200,
  `image/png`, and a nonzero response body.

## Currently Selling Position and Bulk Actions

### Work Completed

- Added a `currently-selling` fragment to the individual Mark-as-sold redirect and
  saved/restored the exact scroll offset for Currently Selling row actions.
- Added accessible row checkboxes, a select-all checkbox, a live selected-row count,
  and Mark selected sold and Delete selected controls.
- Added one validated bulk endpoint and transactional service methods. A missing,
  stale, or already-sold selection fails before any selected row is changed.
- Kept Duplicate as a row-only operation to avoid accidentally creating many new
  listings. Bulk deletion requires explicit browser confirmation.
- Preserved both table sort settings through individual and bulk actions.

### Verification

- Focused Ruff checks passed.
- All 64 Sales service and web tests passed, including atomic bulk updates, bulk
  deletion, selection validation, redirect anchors, and scroll-restoration assets.
- `./scripts/check.sh` passed, including Ruff, all 180 Python tests, package
  compilation, dbt debug and parse, SQLFluff, and the public-file policy.

### Bulk Toolbar Alignment Follow-up

- The Delete selected control inherited the compact icon-only `.delete-button`
  typography and height while Mark selected sold used normal text-button geometry.
- Added a higher-specificity bulk-toolbar rule so both controls share font size,
  line height, minimum height, padding, and centered inline-flex alignment without
  changing compact row-level delete icons.
- Added a static-asset regression test for the shared bulk-button geometry.

## Item-detail Sales Counts

### Work Completed

- Added item-scoped active and sold listing counts to the item-detail response.
- Displayed zero-safe Currently Selling and Sold cards beneath each item's catalog
  metadata.
- Used one aggregate query that derives active count from total listings minus
  listings with a non-null `date_sold`.

### Verification

- Focused Ruff checks passed.
- All 64 catalog service and web tests passed before the final item-isolation and
  zero-count regression assertions were added.
- `./scripts/check.sh` passed after formatting, including Ruff, all 183 Python tests,
  package compilation, dbt debug and parse, SQLFluff, and the public-file policy.

## Persistent Sales Filters and Item Deep Links

### Work Completed

- Added a Sales filter toolbar for item-name substring, exact category, active/sold
  status, inclusive price and computed-profit ranges, and inclusive activity dates.
- Defined activity dates as Selling Since for active rows and Date Sold for completed
  rows, using the same `America/Los_Angeles` calendar dates displayed by the UI.
- Preserved filter state in shareable URLs, independent table-sort links, add/edit
  and row-action forms, bulk actions, and their redirect notices.
- Made the item-detail Currently Selling and Sold count cards link directly to the
  corresponding exact-item Sales view and section anchor.
- Added inline validation for malformed numeric/date values and reversed ranges;
  blank optional form values remain valid.

### Verification

- Ruff passed for all changed Python modules and tests.
- All 69 focused Sales service and web tests passed, including Pacific midnight
  boundaries, combined filters, profit filtering, URL persistence, invalid inputs,
  and item-detail links.
- `./scripts/check.sh` passed, including Ruff, all 187 Python tests, package
  compilation, dbt debug and parse, SQLFluff, and the public-file policy.

## Recipe Profession Levels and Catalog Page

### Work Completed

- Added the standard required profession level beside the profession on item-detail
  recipes. The value is derived from ingredient-slot unlocks rather than incorrectly
  relabeling the live payload's `resultLevel`, which describes the recipe result.
- Added a Recipes top-navigation page that selects the latest recipe for each crafted
  item and derives current item price, recipe cost, profit, and ROI with bulk price
  resolution.
- Added URL-backed filters for item name, category, profession, a two-ended required
  level slider, and profitable, break-even/loss, or unknown economics.
- Made Item, Category, Profession, Required Level, Current Price, Recipe Cost, Profit,
  and ROI independently sortable, with missing values last and rows linking to item
  detail at the recipe section.
- Moved the Sales filter panel below Add an Item to Sell, renamed it Filter Items,
  and made it collapsed by default without changing its persistent filter behavior.
- Kept the operational and BigQuery schemas unchanged because required profession
  level is a governed derivation from existing ordered recipe ingredients.

### Verification

- The real ignored SQLite database rendered all 4,177 latest recipe items in about
  1.3 seconds; a Sword Smith level-filtered response rendered successfully as a much
  smaller page.
- Focused recipe, catalog, and web checks passed before the final full suite.
- `./scripts/check.sh` passed, including Ruff, all 201 Python tests, package
  compilation, dbt debug and parse, SQLFluff, and the public-file policy.

## Hierarchical Item Navigation

### Work Completed

- Reduced the primary navigation to Item and Sales.
- Grouped Item Search and Recipes beneath Item in a native disclosure menu that
  opens on hover, click, or keyboard focus.
- Preserved the active state for both the Item section and the exact submenu page.

### Verification

- Focused Item Search, Recipes, Sales, and static dropdown checks passed.
- `./scripts/check.sh` passed, including Ruff, all 202 Python tests, package
  compilation, dbt debug and parse, SQLFluff, and the public-file policy.

## Recipe Catalog Current Price Editing

### Work Completed

- Replaced read-only Current Price links in Craftable Items with inline fields that
  save on Enter or blur.
- Reused the append-only quantity-one price-observation path, so recipe-page edits
  never create Sales listings.
- Preserved URL-backed filters and sorting across the save, recalculated Current
  Price, Profit, and ROI, and restored the prior scroll offset when browser session
  storage is available.
- Kept invalid values inline with the submitted value and validation message without
  writing a price observation.

### Verification

- Focused rendering, successful update, economics recalculation, state preservation,
  validation, and no-Sales-listing checks passed.
- `node --check` passed for the updated recipe-page script, and all 52 web tests
  passed.
- `./scripts/check.sh` passed, including Ruff, all 204 Python tests, package
  compilation, dbt debug and parse, SQLFluff, and the public-file policy.

## Dual-handle Recipe Level Filter

### Work Completed

- Replaced the two visible Required Profession Level tracks with one shared range
  bar and separate minimum and maximum handles.
- Kept both selected values visible, prevented the handles from crossing, highlighted
  the selected interval, and retained keyboard labels and focus indicators.
- Preserved the existing `min_level` and `max_level` query parameters so filtered
  links and backend behavior remain compatible.

### Verification

- JavaScript syntax and focused recipe-page rendering and validation tests passed.
- `./scripts/check.sh` passed, including Ruff, all 204 Python tests, package
  compilation, dbt debug and parse, SQLFluff, and the public-file policy.

## Multi-item Recipe Calculator

### Work Completed

- Added Recipe Calculator beneath Item navigation with a compact searchable
  craftable-item picker, a removable selected-items table, and per-item craft
  quantities.
- Aggregated repeated resolved ingredients by canonical item identity across every
  selected latest recipe and multiplied their quantities by the requested crafts.
- Added an Ingredients to Buy table with total quantity, current unit price, total
  cost, and consuming items plus an expandable selected-craft cost breakdown.
- Added selected-item, total-craft, unique-ingredient, price-coverage, complete-total,
  and known-cost summary metrics.
- Kept missing prices and unresolved identities explicit and made the calculator a
  read-only request projection with no database migration or operational writes.

### Verification

- Sixteen focused recipe service and web tests passed, including duplicate ingredient
  aggregation, quantity multiplication, current costs, invalid selection handling,
  and rendered shopping-list behavior.
- JavaScript syntax, Ruff, and diff checks passed for the scoped implementation.

## Manual BigQuery Sync Control

### Work Completed

- Added BigQuery Sync as a top-level local page with fixed project, US location,
  `dofus_dev` and `dofus_prod` targets, confirmation, current status, and a
  terminal-style progress panel.
- Wrapped the existing snapshot loader in a process-local background manager that
  rejects overlapping runs, caps the latest timestamped log, and records idle,
  running, succeeded, or failed state.
- Kept command construction server-owned and fixed; the browser cannot submit shell
  commands, database paths, project IDs, dataset IDs, or credentials.
- Added real loader progress at dataset check, raw-table load, manifest publication,
  completion, and already-loaded stages without logging source values.
- Preserved the content-addressed, manifest-last, 1 GB guarded loader behavior and
  documented that dbt Cloud builds remain separate manual actions.

### Verification

- Seventeen focused manager, loader, configuration, and web tests passed without
  contacting Google, covering single-run enforcement, fixed arguments, streamed
  output, success/failure state, manifest-last progress, and absence of source values.
- JavaScript syntax and Ruff checks passed for the scoped implementation.
- The complete `./scripts/check.sh` sequence passed: Ruff, formatting, 211 Python
  tests, compilation, dbt debug and parse, SQLFluff, and the public-file policy.
- Read-only smoke rendering against the ignored real catalog returned HTTP 200 for
  both new pages; no BigQuery publication was started during verification.

## Recipe Workflow Latency and Freshness

### Work Completed

- Profiled the ignored real catalog before changing behavior: Recipes hydrated 4,177
  recipe objects plus 18,943 ingredient relationships on every request and rendered
  a 10.3 MB HTML response; Item Search rendered 11,400 rows in 13.5 MB.
- Replaced the Recipes and Recipe Calculator choice paths with a scalar recipe
  projection, limited Recipe calculation hydration to selected items, and added
  100-row server pages to Recipes and Item Search.
- Enabled response compression for HTML and other responses above 1 KB.
- Added Last Updated (Days) and the exact Missing price, Stale price, and Current
  price states to item-detail recipe ingredients. Age uses UTC calendar dates, and a
  price becomes stale at seven days.
- Added synchronized numeric minimum and maximum inputs beside the dual-handle
  profession-level slider.
- Added row-level Recipe Calculator cart controls to Craftable Items. Browser-local
  UUID/quantity state survives filters and page changes, and Open Recipe Calculator
  submits the cart so the combined ingredient results render immediately.

### Verification

- Ninety-one focused recipe, catalog, and web tests passed, including pagination,
  seven-day freshness, same-day age zero, existing economics, filter state, and
  calculator aggregation behavior.
- JavaScript syntax and Ruff checks passed for the changed files.
- Real-catalog read-only smoke results improved Recipes from about 1.07 seconds and
  10.3 MB to about 0.37 seconds and 307 KB of HTML (about 15 KB compressed). Item
  Search dropped from 13.5 MB to 135 KB of HTML (about 10 KB compressed). The Recipe
  Calculator dropped from about 0.88 seconds to about 0.37 seconds.
- The complete `./scripts/check.sh` sequence passed: Ruff, formatting, 214 Python
  tests, compilation, dbt debug and parse, SQLFluff, and public-file policy.

## Wider Recipes Layout

### Work Completed

- Added a Recipes-only wide content shell with a 100rem maximum and smaller
  responsive side padding so the desktop table uses substantially more viewport
  width.
- Kept the standard 72rem shell on Item Search, item detail, Sales, Recipe
  Calculator, and BigQuery Sync, and retained horizontal overflow for narrow screens.

### Verification

- All 61 focused web and static-asset tests passed.
- The complete `./scripts/check.sh` sequence passed: Ruff, formatting, 214 Python
  tests, compilation, dbt debug and parse, SQLFluff, and public-file policy.

## Editable Recipe Calculator Ingredient Prices

### Work Completed

- Replaced resolved Current Unit Price values in the Combined Shopping List with
  inline editors that save on Enter or blur.
- Added a calculator-scoped JSON mutation that validates comma-formatted positive
  prices and appends a quantity-one price observation through the shared pricing
  service without creating a Sales listing.
- Resubmitted the current calculator selection after a successful edit so the shared
  ingredient row, each selected recipe breakdown, price coverage, and combined cost
  are recalculated immediately from the propagated price.
- Kept unresolved ingredient prices read-only and added inline failure feedback plus
  a successful recalculation notification.
- Updated the public README and architecture description to reflect the calculator's
  narrowly scoped append-only price write.

### Verification

- Focused calculator tests passed for inline controls, invalid-price rejection,
  append-only propagation, a shared-ingredient total changing from 190 to 475, and
  absence of Sales listings.
- The complete `./scripts/check.sh` sequence passed: Ruff, formatting, 214 Python
  tests, compilation, dbt debug and parse, SQLFluff, and public-file policy.

## Out-of-Stock Restocking and Calculator Selection

### Work Completed

- Converted Sales into the same accessible submenu pattern as Item, with Sales
  Activity and the new Out of Stock Items destination.
- Defined out of stock as an item with at least one completed listing and no active
  listing. The grouped projection uses the latest sold row and shows sold count,
  Pacific last-sold date, last sale price, current price, current recipe cost, and
  profit at the last sale price.
- Added Recipe Calculator controls to craftable out-of-stock rows and extracted the
  reusable browser-local cart behavior from the Recipes-only script.
- Separated Recipe Calculator cart membership from calculation selection with a
  second local-storage key, per-row checkboxes, Select all, Select none, and Remove
  all controls.
- Kept unchecked items and quantities in the cart across subset calculations while
  submitting only checked item UUIDs to the existing server-side calculator.
- Disabled unchecked quantity fields, restored non-submitted cart rows after result
  rendering, and retained the existing 100-item server validation boundary.
- Updated README, architecture, and durable project memory for both workflows.

### Verification

- Focused Sales and web tests passed for completed-sales eligibility, active-listing
  exclusion, latest sale/current economics, Sales navigation, calculator actions,
  row checkboxes, subset calculation, and selection-state restoration code paths.
- JavaScript syntax checks passed for the shared cart, Recipes, and Recipe Calculator
  scripts.
- The complete `./scripts/check.sh` sequence passed: Ruff, formatting, 216 Python
  tests, compilation, dbt debug and parse, SQLFluff, and public-file policy.

## Shopping-list Weight, Freshness, Scroll, and Universal Table Sorting

### Work Completed

- Added nullable nonnegative item weight to the operational schema in Alembic
  revision `0006`, JSON responses, the exact BigQuery snapshot contract, dbt staging,
  and `dim_items`.
- Verified the official Dofus Touch exchangeable-item payload uses integer
  `realWeight` values in pods and preserves valid zero weights. The existing live
  catalog sync now enriches matched items without changing UUIDs, prices, recipes,
  provenance, or Sales history.
- Migrated the ignored canonical SQLite database and ran the live catalog sync.
  Weight is populated for 10,927 of 11,400 catalog items; 3,099 values are valid zero,
  and populated values range from 0 through 500 pods. Ten already-known unavailable
  icon downloads still fail independently after weight changes commit.
- Expanded Combined Shopping List rows with Category, Unit Weight, Total Weight,
  Last Updated (Days), and exact Missing price, Stale price, or Current price status.
  Added complete Total Weight and explicit Known Weight summary behavior when any
  ingredient weight is unknown.
- Made Recipe Calculator use the wide desktop shell and a 90rem minimum shopping-list
  table while retaining horizontal overflow on smaller screens.
- Saved and restored the Recipe Calculator scroll offset around a successful inline
  ingredient-price save and recalculation.
- Added one local typed table sorter for text, numeric, and date columns, with stable
  ordering and missing values last. Applied it to item detail recipe/history, Sales
  daily totals, Out of Stock, and every Recipe Calculator table. Existing paginated
  Item Search, Recipes, Currently Selling, and Sold History tables retain server-side
  sorting. Selection and action-only columns are not misleading sort targets.
- Added a guarded BigQuery schema-evolution path so the existing `raw_items` tables
  can gain the new nullable weight column. Unexpected columns, required additions,
  and type or mode changes still stop publication for review.

### Verification

- Focused service, migration, snapshot-loader, API, static-asset, and web tests passed.
- JavaScript syntax checks passed for the shared table sorter and Recipe Calculator.
- The canonical database dry run produced snapshot
  `5d9b8a507bfd4afdf4d2d744a13f215f29d680af78ceeab368373db7f2c18006`
  at schema `0006` without contacting BigQuery.
- `./scripts/check.sh` passed: Ruff lint and formatting, all 221 Python tests,
  compilation, dbt debug and parse, SQLFluff, and the public-file policy.
- No BigQuery publication or dbt Cloud build was started; those remain manual actions
  from the BigQuery Sync page and dbt Studio respectively.

## Page Descriptions and Restock Table Readability

### Work Completed

- Simplified the Recipe Calculator toolbar to report only the number of checked items,
  removing the redundant cart-size phrase.
- Added concise purpose statements beneath the H1 on Item Search, Recipes, Sales,
  Recipe Calculator, Out of Stock Items, BigQuery Sync, and item detail. Market context
  and item metadata remain separate factual lines.
- Diagnosed the concatenated Restock Candidates values as inherited zero cell padding
  intended for Item Search's full-cell links. Added a table-specific spacing rule so
  Sold Count, Last Sold, and the remaining read-only values remain visibly distinct.
- Added regression coverage for the descriptions, simplified count, separate Restock
  cells, and the table-specific spacing rule.

### Verification

- JavaScript syntax validation passed for Recipe Calculator.
- All 66 focused static-asset and web tests passed.
- `./scripts/check.sh` passed: Ruff lint and formatting, all 223 Python tests,
  compilation, dbt debug and parse, SQLFluff, and the public-file policy.

## Combined Shopping List Simplification

### Work Completed

- Removed the Total Crafts summary card and the Unit Weight and Last Updated (Days)
  columns from Combined Shopping List.
- Retained total ingredient weight, freshness Status, craft quantities in the cart
  and selected-craft breakdown, and the underlying calculation fields.
- Reduced the shopping-list minimum width from 90rem to 72rem now that the table has
  fewer displayed columns.
- Updated the public description and regression assertions to match the streamlined
  view.

### Verification

- The focused Recipe Calculator rendering and sortable-table coverage tests passed.
- `./scripts/check.sh` passed: Ruff lint and formatting, all 223 Python tests,
  compilation, dbt debug and parse, SQLFluff, and the public-file policy.
