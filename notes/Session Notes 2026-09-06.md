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
