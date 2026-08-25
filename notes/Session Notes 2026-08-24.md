# Session Notes 2026-08-24

## Out of Stock Restock Recommendations

### Context

Added an inventory recommendation to Out of Stock Items while preventing long gaps
without recorded Sales activity from making items appear slower to sell.

### Work Completed

- Added a sortable Suggested Restock column to the Out of Stock table.
- Calculated sales speed as the average elapsed sales-active days from listing to
  completed sale. A sales-active day is a distinct Pacific calendar date with at
  least one registered completed sale anywhere in the application; dates with no
  registered sales are skipped.
- Suggested three items when the average is at most one sales-active day, two when it
  is above one through five days, and one when it is above five days.
- Kept the calculation read-only and derived from existing listing timestamps, so no
  schema migration or persisted recommendation state was needed.
- Documented the recommendation rule directly on the page and added service and
  rendered-page regression coverage, including a multi-month calendar gap.

### Verification

- Ruff lint and formatting passed.
- All 26 Sales tests passed.
- All 61 relevant web tests passed; the focused Out of Stock service and page tests
  passed.
- The full check reached 246 passing tests out of 247. The unrelated
  `test_profit_opportunities_include_improving_recipes_without_sales_history` failed
  because its hard-coded 2026-08-25 midnight observations are no longer newer than
  the import time on the current UTC date, so its expected historical economics are
  stale. The test was reproduced independently and left unchanged to keep this work
  request-scoped.
- Python compilation, dbt debug and parse, SQLFluff, and the public-file policy all
  passed when run separately after the test-stage stop.

## Sales Prioritization and Calculator Listing Completion

### Context

Tightened the restocking priority display and completed the Recipe Calculator to
Sales handoff so accidental repeat submission cannot duplicate listings and
successfully listed crafts leave the browser-local calculator cart.

### Work Completed

- Defaulted Out of Stock Items to Profit at Last Sale Price descending, with missing
  profits last, and preserved the initial sort indicator and first-click direction in
  the shared client table sorter.
- Added ROI at Last Sale Price as profit divided by the current recipe cost; missing
  profit and missing or zero recipe cost remain explicit.
- Renamed the Sales submenu destination to Activity, moved it to preserve alphabetical
  ordering, and changed the destination page title and H1 to Sales Activity.
- Made Add Checked to Sales single-use per page submission. The first submit marks the
  form in flight and disables its button synchronously; subsequent submits are
  canceled.
- Stored the checked craft UUIDs as transient tab state and removed them from both
  calculator cart membership and calculation selection only on the successful
  `listings-added` Sales redirect. Validation failures clear the pending marker and
  retain the cart.
- Reloaded a browser-cached calculator page on Back navigation when its old table still
  contains crafts removed by a successful Sales handoff.

### Verification

- JavaScript syntax validation passed for `recipe-calculator.js`, `sales.js`, and
  `table-sort.js`.
- Ruff lint and formatting passed.
- All 41 Sales and static-asset tests passed, and all 61 relevant web tests passed.
- The live operational projection returned known profits in descending order with
  missing profits last and calculated ROI without errors.
- The full check reached 246 passing tests out of 248. The previously documented
  date-sensitive Profit Opportunities test still fails. One unrelated bulk-sale test
  also encountered a transient WSL wall-clock rollback between listing creation and
  sale, violated the existing sale-date constraint, and passed immediately in
  isolation without code changes.
- Python compilation, dbt debug and parse, SQLFluff, and the public-file policy all
  passed when run separately after the test-stage stop.
