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

## Deterministic sale-cost test publication

- Kept the sale-cost snapshot test's post-sale observation in the present rather
  than one second in the future, so reopening sees it regardless of machine speed.
  Isolated verification runs the Sales tests before this test-only commit.

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

## Expand Sales Activity filters by default

- Added `open` to Sales Activity's Filter Items disclosure as requested; users can
  still collapse it. Updated the existing rendered-page assertions for its default
  state. The two scoped Sales page/filter tests, Python lint/formatting, and
  `git diff --check` passed. The full script was not repeated for this template-only
  disclosure default after the preceding complete verification. No data changed.
