# Session Notes 2026-09-06

## Download screenshot sales reconciliation

- The user requested all sale records in Downloads. Inspected `IMG_9229.png` and
  `IMG_9230.png` outside the repository and transcribed 35 complete notifications.
  These are distinct login receipts; retained every repeated sale occurrence.
- Applied the established exact-name, latest-recipe profession scope and
  oldest-exact-price-first planner. All identities resolved without ambiguity after
  visually correcting the transcription of Sausshied. Matched 26 active listings;
  nine notifications were non-craftable or outside Tailor, Shoemaker, and Jeweller.
- Used each screenshot's save time, approximately 2026-09-06 17:58:23 Pacific,
  following the established convention. Created an integrity-checked online backup
  before revalidating the plan under a SQLite write lock and applying one transaction.
- Marked all 26 listings sold with manual lineage; corrected one Jellicape price
  from 57,000 to 56,000 through the Sales service and its append-only observation.
  Recorded 1,946,000 kamas revenue, 1,389,130 known recipe cost, and 531,870 known
  profit. Cost coverage is 25 of 26; Mad Boowolf Cloak cost remains unknown.
- Active listings changed from 379 to 353 and sold listings from 413 to 439.
  The ignored report retains source hashes, observed quantities, original plan,
  committed listing identifiers, timestamps, cost snapshots, and backup location:
  `data/reports/manual-screenshot-sales-2026-09-06.json`.
- An independent comparison to the backup confirmed exactly 26 existing listing
  rows changed, one price observation appended, no listing additions or deletions,
  and all other tables unchanged. Every selected price, timestamp, cost (including
  null), and manual lineage matched the report. SQLite integrity and foreign-key
  checks passed. A verification assertion initially failed on the legitimately null
  cost; corrected the read-only assertion and reran verification without any further
  operational writes.
- No application code, schema, dependency, or analytical model changed, so the full
  check script was not run. Operational data, screenshots, report, and backup remain
  ignored or outside the repository.
- The Sales page returned HTTP 200 through the application test client. The
  public-file policy and `git diff --check` passed; Git status contains only MEMORY
  and this session note.

## Sales Price Review page

- Added Sales > Price Review at `/sales/price-review`, alphabetized between Out of
  Stock Items and Profit Opportunities. The page shows one active listing per row
  after seven Pacific calendar days from its latest relist or original listing date.
  Missing-price and one-kama rows remain eligible; catalog-excluded items are omitted.
- Reused existing Sales price history and markdown suggestions. The table provides
  listing age, editable Sales Price, recipe cost, estimated profit, suggested price
  with estimated profit at that price, Selling Since, and Relisted Date. More shows
  category, latest observed item price/date, completed-sale count, and suggestion basis.
  Unknown prices and costs remain explicit; suggestions can expose estimated losses.
- Default ordering is oldest review age first. Eight data columns sort on the server
  with missing values last; 50-row pages retain full due counts and listed value.
  Sorting and page state survive saves; an emptied final page clamps to the last page.
- Enter, blur, and Apply suggestion use the existing append-only Sales price service.
  A successful save records the relisted timestamp, preserves Selling Since and active
  status, and removes only the selected listing until seven more days pass. Item-level
  price observations do not reset listing age. Failed saves retain the entered value
  and show validation or stale-listing errors without appending observations.
- Seven focused test cases cover Pacific date boundaries across DST, recent relists,
  sold/future/excluded rows, missing and minimal prices, per-listing identity, seven-day
  reappearance, current costs and suggested losses, navigation, pagination, sorting,
  valid updates, and validation/not-found/sold conflicts. All 378 Python tests passed.
- Chromium checked navigation, sorting, Enter and blur saves, Apply suggestion,
  invalid-input recovery, pagination, and More details with zero JavaScript errors.
  Layout checks passed at 1440, 900, and 390 pixels; narrow screens scroll within
  the table without page overflow. Browser writes used a disposable synthetic database
  on port 8001; operational records and the user's web process were not changed.
- A read-only GET of the new page against the operational database returned HTTP 200.
  Python route changes require restarting the user's existing `uv run dofus-web` process.
  Updated the stylesheet URL for cache refresh. No migration or dependency change.
- `./scripts/check.sh` passed: Python lint/formatting, 378 Python tests, package
  compilation, dbt debug/parse/seed/build with all 126 nodes passing, SQL lint,
  and the public-file policy. `git diff --check` passed. Stopped the temporary
  preview after browser verification; its synthetic database was removed.

## Default Home page and weekly routine

- Replaced the root Item Search redirect with Home. Added an active Home link to
  the shared navigation and pointed the brand at `/`.
- Followed the user's daily order: mark what sold, craft out-of-stock items, craft
  profitable opportunities, and check the Dashboard. The user chose Monday for
  Price Priorities and Friday for relisting; those tasks join the respective day's
  checklist. The sidebar shows the day's focus and all seven days of the week.
- Reviewed only aggregate operational activity. The available sales history covers
  every weekday, supporting a daily routine. The app has no persisted page-visit or
  click history, so no claims about navigation habits or automatic completion were made.
- Added live cards for today's sales and known revenue, active inventory and known
  asking value, out-of-stock items, and listings due for review. Home uses five scalar
  read queries, with UTC storage and Pacific day boundaries, rather than hydrating
  full recipe or Dashboard projections. Future sales are excluded and unpriced rows
  are counted explicitly. Data remains authoritative in existing operational services.
- Manual checkboxes persist in this browser under one date-keyed localStorage record;
  Up next and progress follow the remaining tasks. State survives refresh and Back,
  synchronizes across tabs, and resets each Pacific day. A stale open/restored page
  refreshes its schedule automatically; links do not complete tasks. Storage failures
  retain usable in-memory checks and show why they cannot persist. Task links also
  work without JavaScript.
- Ten focused Home cases cover all weekdays, date/DST boundaries, counts, missing
  prices, future sales, restocking transitions, read-only behavior, and a fixed small
  query count. Updated root-route and page-description coverage. All 388 Python tests
  passed in the full check sequence.
- Chromium checked keyboard completion, reload/Back persistence, navigation without
  completion, cross-tab updates, all-done behavior, stale-day refresh, previous-day
  reset, malformed state, and denied storage. No JavaScript errors occurred. Light
  and dark layouts fit 1440, 900, 390, and 320 pixels without page overflow.
  Browser writes used a disposable synthetic preview on port 8001.
- No schema or dependency changed. The user's operational records and web process
  were not changed. Restart the existing `uv run dofus-web` process to load Home.
- `./scripts/check.sh` passed: lint/formatting, 388 Python tests, compilation, dbt
  debug/parse/seed/build with 126 passing nodes, SQL lint, and public-file policy.
  Final CTA styling received focused desktop/mobile browser checks after the suite.
  `git diff --check` passed. An operational Home GET returned HTTP 200 with a
  7.0 ms warm median through the test client and approximately 9.7 KB decoded HTML
  in this local sample. Stopped the temporary preview and removed its synthetic data.

## Round Price Review suggestions

- The user requested thousand-rounded suggestions, such as 113,050 to 113,000.
  Applied nearest-thousand rounding to the Price Review projection, with half-thousands
  rounding up and a cap keeping suggestions below the current Sales Price. Suggestions
  below 1,000 retain their positive original amount.
- Display, suggested-price sorting, estimated profit at the suggestion, and Apply
  suggestion share the rounded value. Manual price entry and the existing Sales
  Activity suggestion calculation remain unchanged. Updated the page explanation.
- Added focused coverage for rounding down/up, halfway values, exact thousands,
  completed-sale-median suggestions, the below-current-price cap, and sub-1,000
  prices. Verified the rendered amount and Apply form value, then the persisted
  asking price and linked observation. Updated the existing suggestion-profit test.
- All 119 focused Price Review, Sales service, and web tests passed, along with
  Python lint/formatting, public-file policy, and `git diff --check`. The full
  check script was not repeated for this small calculation/template change after
  the preceding full pass. No operational prices were changed during this task.

## Alphabetical Price Review default

- Changed Price Review's default service, GET, and price-update sort state to item
  name ascending (A–Z), as requested. Explicit alternate sorts remain available and
  continue through saves and pagination.
- All 14 Price Review tests passed, plus scoped Python lint/formatting, public-file
  policy, and `git diff --check`. A disposable synthetic app verified case-insensitive
  alphabetical ordering, save-form sort state, and explicit age sorting. The full
  check script was not repeated for this default-only change. No operational data changed.

## Remote publication

- The user requested a push. Local `main` and `origin/main` began at the same
  commit. Separated sales-reconciliation notes, the complete Price Review feature
  (including rounded suggestions and alphabetical defaults), and Home into three
  logical commits, preserving the final working content.
- Exported the staged Price Review tree to an isolated temporary directory: all
  119 focused Sales/Price Review/web tests and Python lint/formatting passed before
  committing it. The final combined `./scripts/check.sh` passed with 395 Python
  tests, 126 dbt nodes, SQL lint, compilation, and the public-file policy.
- Staged only the reviewed source, tests, architecture, and project notes. Checked
  working and staged whitespace. Private operational databases, screenshots,
  reports, backups, and credentials remain excluded. Publication uses a normal
  fast-forward push to `origin/main`.

## Snooze, fourteen-day review, and separate relist entry

- The user requested an Action column with Snooze, a 14-day review threshold, and a
  separate empty Relist Price column. Price Review now shows the recorded Sales
  Price as read-only and accepts a new price in the blank Relist Price field.
  Enter/blur saves retain the existing append-only observation and relisted-date
  behavior, including deliberate relisting at the same price. Rounded suggestions,
  alphabetical defaults, alternate sorting, and pagination remain available.
- Changed the shared review threshold to 14 Pacific calendar days after listing or
  latest relist. Snooze persists a separate nullable `price_review_snoozed_until`
  timestamp and hides only that listing until exactly seven 24-hour days after the
  click. Snooze never changes price, observations, listing start, or relist date.
  Repricing clears it and starts a new 14-day review period. Home counts and shared
  Activity, Dashboard, and Insights review reminders exclude unexpired snoozes.
- Snooze validates that a listing is active, in the visible catalog, and due for
  review. Guarded repository updates reject duplicate/stale snoozes and concurrent
  price changes, with failed writes rolled back. The ORM update uses database-side
  synchronization to avoid comparing naive SQLite timestamps with aware datetimes.
- Added Alembic `0011` using a direct nullable column addition. Existing migration
  tests verify upgrade/downgrade with dependent records and default-null snooze data.
  Backed up the canonical operational database online, applied `0011`, and compared
  every preexisting column in every application table with the backup: all values
  were preserved, all snoozes initially null, integrity check OK, no foreign-key
  violations. The ignored report records the backup and verification results at
  `data/reports/price-review-snooze-migration-0011.json`.
- The initial full suite caught the exporter's intentionally strict schema contract.
  Added the nullable snooze timestamp to the raw snapshot contract and verified
  timestamp serialization and additive BigQuery schema compatibility with a fake
  client. A live operational snapshot dry run passed at schema `0011`; no BigQuery
  write or hosted build was performed.
- Updated boundary fixtures for 14 days and tested persistent snooze, exact expiry,
  repeated snooze after expiry, duplicate submissions, active/young/sold/missing
  listing errors, per-listing isolation, Home/reminder consistency, and clearing
  snooze on relist. All 397 Python tests passed.
- Chromium verified separate read-only Sales Price and blank Relist Price fields,
  harmless focus/blur on an empty field, Snooze and refresh persistence, Home's due
  count with unchanged inventory, same-price relisting, Enter/blur saves, validation
  recovery, and Action visibility. No JavaScript errors; table scrolling stayed
  contained at 1440, 900, and 390 pixels. All browser mutations used disposable
  synthetic records on the temporary port-8001 preview.
- Read-only operational Home, Price Review, Sales Activity, and Dashboard requests
  all returned HTTP 200 after migration. Stopped the temporary preview and removed
  its synthetic database. The user's running web process was left under their control;
  restart `uv run dofus-web` to load the Python changes. No manual migration remains.
- Final `./scripts/check.sh` passed: 397 Python tests, lint/formatting, compilation,
  dbt debug/parse/seed/build with all 126 nodes passing, SQL lint, and public-file
  policy. `git diff --check` passed. Only scoped source, migration, tests, and docs
  are in Git status; the operational database, backup, and migration report are ignored.

## Sales Activity cleanup and dashboard decision context

- Removed Add an Item to Sell from Sales Activity, its initial picker query, and
  browser picker handlers. Existing creation endpoints and Recipe Calculator sales
  remain available. Listing management, filters, pagination, bulk actions, chart
  toggles, and price autosave remain intact.
- Investigated the August 22 Daily Realized Profit dip using read-only operational
  SQLite and the running UI. The negative amount was a known-profit subtotal for
  five of 39 sales (12.8% cost coverage); 34 costs were unknown. It did not represent
  the entire day's result. All five costs were reconstructed from historical
  observations rather than stored sale-time snapshots. No source-value correction
  was justified and no operational records were changed.
- Daily Realized Profit now plots only days with complete cost coverage, plus zeros
  for no recorded sales. Incomplete days have a gap and a separate outlined square
  below the plot. Pointer, touch, or keyboard focus reveals the covered sale count
  and known-profit subtotal. Complete losses remain below zero. Headline known
  profit and the daily table retain partial subtotals; the table labels incomplete
  days and explains why total revenue minus covered cost is not known profit.
- Added Category multi-select and normalized item-name substring filters. Category
  selections combine with OR, and the name query combines with AND. Filters apply
  consistently to both comparison periods, daily charts, KPIs, top items, latest
  sale, and current inventory across all dates. Time links preserve the query;
  Clear filters retains the period. Choices remain available with no matches.
- Added service and rendered-route regression coverage for incomplete negative
  subtotals, full-cost losses, zero-sale days, filter combinations, current/prior
  period consistency, inventory/reminders, query retention, and empty results.
  Updated former add-form assertions. The full suite exposed an existing timing
  dependency in a Sales snapshot test: its new observation was one second in the
  future but expected to be current when reopening. Using the actual post-sale
  observation time makes that test independent of machine speed.
- Chromium checked coverage-marker focus, preserved complete losses, category/name
  filters, period switching, reset, empty results, and Sales Activity. Layouts at
  1440, 900, and 390 pixels had no horizontal page overflow or JavaScript errors.
  All browser records were disposable synthetic fixtures on temporary port 8001.
- A read-only TestClient against the operational database verified August 22 is
  explicitly incomplete with 5 of 39 costs known and its original subtotal retained
  in details. Filtered Dashboard and Sales Activity requests returned HTTP 200.
- Final `./scripts/check.sh` passed: all 400 Python tests, Python lint/formatting,
  compilation, dbt debug/parse/seed/build with 126 passing nodes, SQL lint, and
  public-file policy. `git diff --check` passed. Stopped the temporary preview;
  the existing web process remains under the user's control and needs a restart
  to load these changes. Existing uncommitted Price Review work was preserved.

## Price entry in thousands of kamas

- The user requested 77 to mean 77,000 in Listings Due for Review and throughout
  the web UI. Added a visible ×1,000 kamas unit beside every price-entry field,
  accessible unit descriptions, decimal keyboards, and page help with examples.
  Existing values and unchanged-value baselines display in the same scale. Blank
  Relist Price entry remains blank. Decimals support smaller prices (0.5 = 500;
  0.001 = 1) without rounding existing prices or losing whole-kama precision.
- Applied the convention to Price Review, Sales Activity, Item Search/detail,
  Price Priorities, Recipes, Recipe Calculator ingredients and bulk Sale Price
  Each, plus Sales minimum/maximum price filters. Read-only prices, history,
  summaries, profit filters, stored values, and JSON API commands remain full kamas.
- New HTML forms explicitly carry `price_unit=thousands`; shared web-boundary
  conversion uses Decimal before the existing command validation. Up to three
  decimal places are accepted, while fractions of a kama and malformed prices are
  rejected without rounding. Unmarked legacy forms and hidden Apply suggestion
  forms retain canonical full-kama values, preventing an accidental second scale.
- Calculator live profit/projected-sales calculations expand entered prices once;
  two crafts at 77 correctly produce 154,000 projected sales. Ingredient saves,
  recalculation, selected-quantity handling, and atomic bulk listing creation use
  canonical stored prices. Filter links preserve canonical query values while the
  rendered price-filter fields retain the thousands scale.
- Added conversion/validation, endpoint, relisting, ingredient, bulk calculator,
  and filter regression tests. Updated price-prefill assertions while retaining
  checks that observations, recipe costs, profits, and full-kama legacy writes
  stay correct. All 420 Python tests passed.
- Browser verification used only a disposable synthetic SQLite preview on port
  8001. Checked all price-entry surfaces, Enter/blur autosave, invalid-value recovery,
  suggestions, relist removal, small ingredient prices, calculator live totals,
  recalculation, and two 77,000-kama bulk listings. No JavaScript errors. Desktop
  and mobile checks at 1440, 900, and 390 pixels passed. Scoped positioning keeps
  hidden labels inside price editors/calculator table scroll containers, fixing
  the small-screen overflow exposed by those checks.
- Full `./scripts/check.sh` passed with 420 Python tests, all 126 dbt nodes,
  compilation, Python/SQL lint, formatting, and public-file policy. After the final
  CSS containment adjustment, browser checks and Python lint/formatting plus
  `git diff --check` passed again. No operational database values or schema changed;
  the existing user web server was left running and requires a restart to load
  the Python changes. Earlier uncommitted work remains preserved.

## Full-kama ingredient prices and craftable-item units

- The user clarified that Per Unit Price must remain literal kamas and the
  thousands shortcut is intended for expensive craftable items. Restored full
  kama prefills, baselines, numeric keyboards, labels, and submissions for ingredient
  prices in both item-detail recipes and Recipe Calculator. Entering 77 now saves
  77 kamas in either ingredient editor, including craftable intermediate ingredients.
- Item Search/detail and Price Priorities choose the price-entry unit by recipe
  membership: craftable output prices use thousands; other items use full kamas.
  Search and priority views add one bulk recipe-membership query for displayed
  rows. Field labels and page help explain both units. Price Review, Sales prices,
  Recipes, and calculator Sale Price Each retain the thousands shortcut.
- Kept explicit HTML unit markers, canonical persistence/API amounts, and support
  for previously rendered marked forms. No stored prices were reinterpreted or
  changed. Updated prefill assertions and added mixed-page unit/save checks covering
  raw materials, craftable outputs, priority items, and literal calculator units.
- Chromium verified Item Search raw-material edits, craftable item edits, both
  ingredient editors, calculator profit/revenue calculations, and two 77,000-kama
  bulk listings using a disposable synthetic preview. No JavaScript errors or page
  overflow at 1440/390 pixels. Stopped the temporary port-8001 preview; the user's
  existing web process is unchanged and requires a restart for the Python changes.
- Final `./scripts/check.sh` passed: 421 Python tests, all 126 dbt nodes,
  Python lint/formatting, compilation, SQL lint, and public-file policy.
  `git diff --check` passed; private databases and generated artifacts remain ignored.

## Restore the Daily Realized Profit line

- The prior complete-cost-only rendering hid nearly every active day in the
  current report, leaving disconnected line fragments. A read-only operational
  check found 15 incomplete days and only two separate visible line segments.
- Restored each day's known-profit subtotal to the plotted series, matching the
  headline and daily table. Segments touching partial-cost days are dashed and
  those points are hollow, with explicit coverage and subtotal readouts. Days with
  entirely unknown profit still have gaps and separate markers; no-sale days stay
  zero. No missing value is interpolated or treated as profit.
- Removed the now-unused complete-profit property. Updated the legend and chart
  explanation, and regression tests cover consecutive partial days, complete
  losses, zero activity, and entirely unknown days without invented connections.
- The operational 30-day report now renders all 30 available values and 29
  connecting segments, including 16 clearly marked partial segments. No database
  values were changed. Synthetic Chromium checks passed for chart focus/readouts,
  losses, dashboard filters, and 1440/900/390-pixel layouts without JavaScript errors
  or page overflow. The temporary preview was stopped; the existing user server
  remains under user control and needs a restart for the changed Python code.
- Final `./scripts/check.sh` passed: 422 Python tests, all 126 dbt nodes,
  Python/SQL lint, formatting, compilation, and public-file policy.
  `git diff --check` passed; operational data and preview artifacts remain ignored.

## Expand Sales Activity filters by default

- Added `open` to Sales Activity's Filter Items disclosure as requested; users can
  still collapse it. Updated the existing rendered-page assertions for its default
  state. The two scoped Sales page/filter tests, Python lint/formatting, and
  `git diff --check` passed. The full script was not repeated for this template-only
  disclosure default after the preceding complete verification. No data changed.

## Deterministic sale-cost test publication

- Kept the sale-cost snapshot test's post-sale observation in the present rather
  than one second in the future, so reopening sees it regardless of machine speed.
  Isolated verification runs the Sales tests before this test-only commit.

## Remote publication verification

- Prepared the pending changes as five focused commits covering the timing test,
  Price Review, Sales Activity, Dashboard, and price-entry units.
- Re-ran `./scripts/check.sh` against the complete final implementation: 422 Python
  tests passed, all 126 dbt build/test nodes passed, and lint, formatting, SQL lint,
  compilation, and the public-file policy passed. Each intermediate implementation
  also received isolated lint, formatting, and relevant Python test checks.
- Checked staged changes for whitespace errors and kept operational databases,
  raw exports, generated artifacts, and local verification logs out of Git.

## Price Priorities units

- Price Priorities Current Price now uses literal full kamas for every item,
  including craftable items. Updated the help text, field labels, unit marker, and
  input mode, and removed the recipe-membership query that this page no longer needs.
- Updated existing checks for full-kama priority submissions. All 101 focused web,
  price-unit, and Sales Activity tests passed, along
  with Python lint/formatting, public-file policy, and `git diff --check`.
  The full dbt check sequence was not repeated for these small web-only changes.

## Bottom navigation for every paginated section

- Reused the existing pagination controls below Currently Selling, preserving its
  filters, sorting, and the independent Sold History page.
- Audited all pagination templates and added the existing Sold History pagination
  below its table. Item Search, Recipes, Price Review, and Currently Selling already
  had bottom navigation; every paginated section now provides it.
- Reused Sold History's existing page state and URLs, preserving filters, sorting,
  and the independent Currently Selling page. All 96 focused web, Sales Activity,
  and Price Review tests passed, as did Python lint/formatting and `git diff --check`.
  The full dbt check sequence was not repeated for this template-only addition.

## Uniform Dashboard profit line

- Daily Realized Profit now uses the same solid line and filled points for every
  plotted day, including days with incomplete costs. Removed the dashed/hollow
  legend, unused styles, and separate segment grouping, and refreshed the CSS URL.
- Preserved daily known-profit values, coverage details in readouts, and gaps where
  profit is wholly unknown. No cost or sales records changed.
- Updated existing chart and rendered-page checks. All 104 focused Dashboard, web,
  and static-asset tests passed, as did Python lint/formatting, public-file policy,
  and `git diff --check`. The full dbt sequence was not repeated for this web chart
  presentation change.
