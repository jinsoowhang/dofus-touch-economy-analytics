# Session Notes 2026-09-04

## Download screenshot sales reconciliation

### Request and interpretation

- The user supplied the Downloads directory containing `IMG_9222.png` and
  `IMG_9226.png`. Both screenshots remained outside the repository.
- The images contained 38 complete sold-notification occurrences. Their sequences
  did not align, and their distinct game scenes indicated separate character/login
  receipts rather than overlapping scroll captures, so every complete occurrence
  was retained for reconciliation.
- The user did not supply a separate sale time. Both images therefore use their
  shared local save time, 2026-09-04 17:19:09.725862 America/Los_Angeles.

### Reconciliation and operational update

- Rehearsed the combined occurrence list through the deterministic sold-capture
  planner. Twenty occurrences resolved to exact active catalog items with latest
  Tailor, Shoemaker, or Jeweller recipes and sufficient active Sales listings.
- Eighteen occurrences remained unchanged by design: thirteen had no latest recipe,
  two were Alchemist items, two were Hunter items, and one was a Miner item.
- Atomically marked the 20 in-scope listings sold with manual lineage. Exact-price
  candidates were reserved first, then listings were selected oldest-first.
- Corrected the selected Jellicape Sales Price from 57,000 to the screenshot's
  56,000 kamas and appended its linked quantity-one price observation in the
  configured `unspecified` market context.
- Created ignored integrity-checked online backup
  `data/app/backups/dofus-touch-before-manual-screenshot-sales-2026-09-04-20260905T002223161432Z.sqlite3`
  before mutation.

### Result and verification

- Recorded 20 sales and 1,927,000 kamas revenue. Recipe cost is known for all 20:
  1,528,043 kamas cost and 398,957 kamas realized profit.
- Active listings changed from 316 to 296, and completed listings changed from 345
  to 365.
- An independent query confirmed all 20 selected rows have the intended timestamp,
  screenshot prices, and manual sale lineage. The only price observation at that
  timestamp is the Jellicape correction in the configured market context.
- SQLite integrity is `ok` for both the live database and recovery backup. The Sales
  page rendered successfully through the application test client.
- No application code, screenshot, local database, or backup was added to Git. The
  full check suite was not run because application code, schemas, dependencies, and
  model behavior were unchanged.

## Profit Opportunities profession-level filter

### Request and implementation

- Added a URL-backed maximum profession-level filter to Profit Opportunities and
  defaulted the page to level 60.
- The route accepts levels 1 through 100 and applies the selected maximum through
  the recipe service before summary metrics, ranking, and the 100-row display limit.
- Kept the default page behavior scoped to Profit Opportunities; the unfiltered
  recipe-service call used by Insights remains unchanged.
- Added the derived Profession Level as a visible sortable numeric column in Current
  Opportunities and removed its duplicate row-detail entry.

### Verification

- Added service coverage proving a profitable level-100 recipe is excluded at level
  60 and included at level 100, plus web coverage for the default and overridden
  form values.
- `./scripts/check.sh` passed: 353 Python tests, dbt debug/parse/seed/build with all
  126 build nodes passing, SQL lint, and the public-file policy.
- `git diff --check` passed before the session-note update.
- Reproduced the user's live level-filter failure against a web process started
  before the Python changes. Jinja had picked up the new form and column, while the
  stale route and service still ignored `max_level`.
- Restarted the loopback-only `dofus-web` process with the same default project
  configuration. A live `max_level=60` request returned 100 rows with level 60 as
  the highest and zero rows above the cap; `max_level=100` returned level-80 rows as
  expected.

## Recipe cart Back-navigation state

### Request and implementation

- Profit Opportunities could retain stale `Added` button text after an item was
  explicitly removed in Recipe Calculator and the browser navigated Back.
- The shared cart script had captured local-storage state only at initial execution;
  a back/forward-cache restore reused that stale in-memory state and DOM.
- Added a `pageshow` handler for cached restores that rereads both cart membership
  and calculation selection before rendering every shared cart button.
- Preserved the existing distinction between unchecking a calculator row, which
  keeps it in the cart, and explicitly removing the row, which returns entry-point
  buttons to Add.

### Verification

- Added focused static-asset coverage for cart and selection resynchronization on a
  persisted `pageshow` event.
- `./scripts/check.sh` passed: 354 Python tests, dbt debug/parse/seed/build with all
  126 build nodes passing, SQL lint, and the public-file policy.
