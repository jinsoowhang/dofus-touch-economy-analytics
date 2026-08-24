# Session Notes 2026-08-23

## Context

Fixed a Recipe Calculator regression where updating an inline unit price in the
Combined Shopping List discarded the user's client-side table ordering after the
calculator reloaded its results.

## Work Completed

- Confirmed that the inline price flow already preserved scroll position but lost the
  active client-side sort because the full calculator resubmission replaced the DOM.
- Saved the active Combined Shopping List column index and ascending or descending
  direction in one-time session storage after a successful price update.
- Restored that ordering through the shared typed table sorter before restoring the
  saved scroll position, then removed the transient sort state.
- Added focused static-asset regression coverage for capturing and restoring both sort
  directions.

## Verification

- JavaScript syntax validation passed for `recipe-calculator.js`.
- All 68 focused static-asset and web tests passed.
- `./scripts/check.sh` passed: Ruff lint and formatting, all 229 Python tests,
  compilation, dbt debug and parse, SQLFluff, and the public-file policy.

## Selected Craft Breakdown Full-Width Layout

### Context

Fixed the Selected craft breakdown layout after a screenshot showed its help text and
button in the left half while the sales table was constrained to the right half with
unnecessary horizontal scrolling.

### Work Completed

- Traced the split layout to the site-wide two-column `form` grid applying to the
  calculator sales form.
- Scoped that form to block layout so its help text, table, and action stack at full
  content width.
- Added spacing above the action and focused stylesheet regression coverage.

### Verification

- All 69 focused static-asset and web tests passed.
- `./scripts/check.sh` passed: Ruff lint and formatting, all 230 Python tests,
  compilation, dbt debug and parse, SQLFluff, and the public-file policy.

## Selected Craft Total Estimated Profit

### Work Completed

- Added a sortable Total Estimated Profit column to every Selected craft breakdown
  row.
- Defined the row measure as Sale Price Each multiplied by Quantity minus Total Recipe
  Cost and documented the formula beside the table.
- Rendered the initial measure from each whole current-price default and complete
  recipe cost.
- Recalculated the displayed value and numeric sort value on every valid sale-price
  edit; missing, invalid, or incomplete inputs remain an explicit em dash.
- Increased the table's minimum width to accommodate the new decision column without
  crowding the existing Sales controls.

### Verification

- JavaScript syntax validation passed for `recipe-calculator.js`.
- All 84 focused Recipe Calculator, recipe-service, web, and static-asset tests passed.
- `./scripts/check.sh` passed: Ruff lint and formatting, all 230 Python tests,
  compilation, dbt debug and parse, SQLFluff, and the public-file policy.

## Selected Craft Category and Live Profit Regression

### Work Completed

- Carried each crafted catalog item's existing category through the Recipe Calculator
  selected-item projection.
- Added sortable Category directly after Profession in Selected craft breakdown and
  kept missing values explicit as Uncategorized.
- Expanded the table width for the added decision column.
- Preserved immediate Total Estimated Profit recalculation on Sale Price Each input
  and added an explicit regression assertion for the browser input listener.

### Verification

- JavaScript syntax validation passed for `recipe-calculator.js`.
- All 84 focused Recipe Calculator, recipe-service, web, and static-asset tests passed.
- `./scripts/check.sh` passed: Ruff lint and formatting, all 230 Python tests,
  compilation, dbt debug and parse, SQLFluff, and the public-file policy.

## Recipe Calculator Similar-Craft Suggestions

### Context

Added cart-aware craft recommendations so a player selecting multiple recipes can
identify other crafts that reuse the same ingredients and reduce repeated crafting
setup work.

### Work Completed

- Added an exact ingredient-overlap projection over the latest recipe per crafted
  item. Resolved ingredients match by canonical item identity and unresolved
  ingredients match by normalized source name.
- Excluded recipes already in the cart and candidates with no shared ingredients,
  then ranked up to ten suggestions by candidate-recipe coverage, shared ingredient
  count, number of cart recipes overlapped, and item name.
- Added a validated, read-only JSON endpoint for browser-local cart UUIDs; malformed,
  duplicate, stale, undersized, and oversized selections remain explicit errors.
- Added a Suggested Similar Crafts panel under Select Craftable Items. It shows the
  shared count, percentage, and cart-item breadth for each recommendation and adds a
  suggested craft directly to the persistent cart.
- Refreshed suggestions after cart additions, removals, and local-storage restoration;
  debouncing and request cancellation prevent stale results during quick edits.
- Added service ranking/exclusion coverage plus endpoint, validation, template, and
  browser-wiring regressions.

### Verification

- JavaScript syntax validation passed for `recipe-calculator.js`.
- Focused recipe-service and Recipe Calculator web tests passed.
- `./scripts/check.sh` passed: Ruff lint and formatting, all 231 Python tests,
  compilation, dbt debug and parse, SQLFluff, and the public-file policy.

## Item Recipe Actions and Sales Opportunity Discovery

### Context

Expanded crafting and Sales decision support across Item detail, a new opportunity
page, and Best Sellers while reducing the horizontal scrolling required to inspect
Sales Performance on a desktop without touchpad gestures.

### Work Completed

- Added the crafted item's catalog Category between Profession and Required Level in
  the Item Recipe heading.
- Added the shared browser-local Recipe Calculator cart controls to craftable Item
  detail pages without changing price or Sales persistence.
- Added Profit Opportunities to the Sales submenu and a wide, sortable page that
  evaluates every fully priced, currently profitable latest recipe, including items
  with zero completed Sales.
- Bulk-selected each ingredient's current and immediately previous valid observation.
  Prior ROI holds the current crafted-item price fixed, so positive ROI change reflects
  ingredient-cost improvement rather than output-price movement.
- Labeled opportunities Improving when ROI increased, Newly Priced when no complete
  prior recipe cost exists, and Profitable Now otherwise; ranked up to 100 in that
  signal order and surfaced current profit, ROI, ROI change, top profit, and top ROI.
- Replaced Best Sellers Price Coverage with Top Profit, defined as the highest
  complete current estimated per-item profit among items with completed Sales.
- Reduced the Best Sellers table minimum width from 105rem to 64rem. Kept its primary
  decision columns visible and moved Category, average price, average time to sell,
  active count, current price, and recipe cost into native More disclosures that work
  with mouse, keyboard, and touch rather than hover alone.
- Added service, routing, navigation, template, cart-action, responsive-table, and
  zero-sales opportunity regressions.

### Verification

- The local operational database completed the new read-only opportunity scan in
  1.84 seconds including Python startup; its current state contains zero fully priced
  profitable recipes, and the page renders guidance for that empty state.
- `./scripts/check.sh` passed: Ruff lint and formatting, all 234 Python tests,
  compilation, dbt debug and parse, SQLFluff, and the public-file policy.

## Recipe and Item Decision-Flow Refinements

### Context

Fixed a Recipes level-filter input regression and tightened several recipe, price
history, and Best Sellers decision surfaces.

### Work Completed

- Separated live dual-range track updates from committed endpoint-order enforcement,
  so typing a multi-digit maximum no longer truncates an existing minimum after the
  first digit.
- Deduplicated Item Price History for presentation by UTC Date Observed and total
  price. The newest valid matching observation supplies the displayed row and delete
  action, while all append-only observations remain in the audit history.
- Added a sortable Currently Selling count to the Recipes catalog and linked each
  count to that item's active Sales filter.
- Changed the Item Recipe action label to Add to Recipe Calculator while preserving
  the shared cart's shorter default label on other pages.
- Moved Top Profit between Most Units Sold and Top Revenue in the Best Sellers
  summary.
- Added focused service, web, template-order, and browser-wiring regression coverage
  for all five changes.

### Verification

- JavaScript syntax validation passed for `recipes.js` and `recipe-cart.js`.
- All 91 focused recipe, web, and static-asset tests passed.
- `./scripts/check.sh` passed: Ruff lint and formatting, all 237 Python tests,
  compilation, dbt debug and parse, SQLFluff, and the public-file policy.

## Active Price Reviews and Navigation Interaction

### Context

Added an actionable review for older active listings, corrected overlapping Item and
Sales menus shown in a desktop screenshot, alphabetized submenu links, and fixed the
remaining Recipes numeric-range peer mutation.

### Work Completed

- Added price reviews for Currently Selling listings after seven Pacific calendar
  days. Suggestions use the lower of a 5% markdown or the item's all-time completed-
  sale median, and identify the calculation basis and sale sample count.
- Kept suggestions advisory: no background or page-load mutation occurs. An explicit
  Apply suggestion action uses the existing audit-preserving Sales repricing flow and
  preserves Sales filters, sorting, and scroll position.
- Added the due-for-review count to the Currently Selling summary and kept the
  recommendation inside the existing Sale Price cell instead of adding a column.
- Alphabetized Item and Sales submenu links.
- Removed hover-only submenu exposure, enforced at most one open menu, and close the
  active menu after outside pointer/focus interaction or Escape.
- Split Recipes range rendering from numeric synchronization. Numeric input now
  updates only its own range value, and committed invalid ordering constrains the
  edited endpoint without mutating its peer.
- Added service, rendered workflow, navigation wiring, submenu order, and range peer-
  isolation regressions.

### Verification

- JavaScript syntax validation passed for `site-navigation.js` and `recipes.js`.
- All 99 focused Sales, web, and static-asset tests passed.
- `./scripts/check.sh` passed: Ruff lint and formatting, all 239 Python tests,
  compilation, dbt debug and parse, SQLFluff, and the public-file policy.

## Recipe Calculator Craft Links

### Work Completed

- Linked each craft name in Select Craftable Items to its Item detail page.
- Applied the same link to server-rendered selections and rows added or restored by
  the browser so cart interaction does not change navigation behavior.
- Added focused rendered-page and browser-wiring regression coverage.

### Verification

- JavaScript syntax validation passed for `recipe-calculator.js`.
- The focused Recipe Calculator web regression passed.
- `./scripts/check.sh` passed: Ruff lint and formatting, all 239 Python tests,
  compilation, dbt debug and parse, SQLFluff, and the public-file policy.

## Profit Availability, Multi-Select Filters, and Catalog Exclusions

### Context

Improved opportunity discovery by sale availability, allowed broader catalog and
recipe comparisons, and removed a confirmed Dofus-only item from active Dofus Touch
workflows without destroying imported provenance.

### Work Completed

- Added a Show only items not currently selling checkbox to Profit Opportunities.
  The service filters on zero active listings before summary calculations and the
  100-row display limit.
- Labeled each opportunity with its current active-listing count or an explicit Not
  currently selling state, and retained active plus completed counts in row details.
- Replaced Item Search's single Category select with a checkbox-style multi-select.
  Repeated category query values use OR and persist through HTMX searches, sorting,
  and pagination.
- Replaced Recipes' single Category and Profession selects with checkbox-style
  multi-selects. Values use OR within each group and AND across category,
  profession, name, level, and economics groups; sorting, pagination, and inline
  price-update redirects preserve repeated parameters.
- Verified Violet Arrow Helmet was absent from Ankama's live Dofus Touch catalog.
  Added a curated normalized-name exclusion shared by catalog reads, recipe and
  calculator projections, icon targets, and new price and Sales writes.
- Rejected manual attempts to recreate an excluded item while retaining the private
  CSV source row, imported recipe, and prior price observation for auditability.
- Deliberately avoided bulk-removing every exact-name miss from the live catalog
  comparison because many legitimate Touch items use legacy or aliased names.

### Verification

- Focused Profit Opportunities service and web tests passed.
- All 101 catalog, recipe, and web tests passed after the multi-select changes.
- All 92 affected catalog, recipe, API, icon-fetch, and Sales tests passed after the
  catalog exclusion.
- `./scripts/check.sh` passed: Ruff lint and formatting, all 241 Python tests,
  compilation, dbt debug and parse, SQLFluff, and the public-file policy.

## Crafting and Sales Decision Controls

### Context

Added missing operational counts to crafting decisions, made the Sales chart directly
comparable, used available opportunity-table width, and corrected the oversized
multi-value filter layout shown in the desktop screenshot.

### Work Completed

- Added current-listing and completed-sale counts to each Suggested Similar Crafts
  projection and compact browser-rendered row beside item, profession/level, shared
  ingredients, and Add.
- Replaced the Sales Over Time display-only legend with checked Sales, Cost, and Profit
  controls. Users can show any one, two, or all three series; the browser prevents an
  empty chart.
- Added a visible sortable Currently Selling column to Current Opportunities and
  removed its redundant secondary listing label.
- Changed checkbox-style multi-value menus into bounded overlay popovers and scoped
  their checkbox/input geometry so opening Category or Profession no longer expands
  the form grid, moves the page, or renders oversized options.

### Verification

- JavaScript syntax validation passed for `recipe-calculator.js` and `sales.js`.
- Six focused recipe-service, Sales, web, and static-asset regressions passed.

## Authoritative Dofus Touch Catalog Reconciliation

### Context

Replaced the one-item exclusion with a comprehensive, repeatable comparison against
Ankama's current Dofus Touch client catalog while retaining operational provenance.

### Work Completed

- Added schema 0007 fields for nullable verified/excluded membership status, the UTC
  check timestamp, and an exclusion reason. The migration seeds the already confirmed
  Violet Arrow Helmet exclusion without deleting its source or economic history.
- Extended the live catalog sync to compare every local item with every current
  English Touch item name, including non-exchangeable items, while accepting reviewed
  legacy-name aliases. Exact matches also adopt official display-name casing.
- Applied the live pass to all 11,400 local items: 10,948 are verified and 452 are
  excluded. `Chouquish Belt` now has official casing; Violet Arrow Helmet and Violet
  Arrow Cape are excluded.
- Centralized website scope on persisted status. Search, item detail, recipes, Recipe
  Calculator, prices, Sales, and icon targets hide excluded items, and recipes with an
  excluded resolved ingredient are hidden. Unchecked items remain visible until a
  successful sync, and excluded rows remain available for audit.
- Added the membership fields to the exact SQLite snapshot contract, BigQuery nullable
  schema evolution, dbt staging, and `dim_items`, with documentation of their grain and
  provenance behavior.
- Preserved the existing icon-cache result: ten items in the official payload still
  have unavailable upstream icon files, but status reconciliation and capitalization
  completed before those download failures were reported.

### Verification

- All 61 focused migration, catalog-sync, catalog-service, recipe, and analytics
  snapshot tests passed.
- The real database migrated from 0006 to 0007 and read-only checks confirmed 10,948
  visible verified rows, 452 excluded rows, and 83 recipes with excluded dependencies
  that are now suppressed.
- `./scripts/check.sh` passed: Ruff lint and formatting, all 246 Python tests,
  compilation, dbt debug and parse, SQLFluff, and the public-file policy.
