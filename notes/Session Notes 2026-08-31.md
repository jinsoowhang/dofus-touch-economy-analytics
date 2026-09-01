# Session Notes 2026-08-31

## README Slack worker launch command

### Documentation

- Added `uv run --env-file .env.slack dofus-slack-worker` to the main local setup
  flow in the README.
- Clarified that the worker runs in a second terminal alongside the blocking local
  web process and only after completing the private Slack setup.
- Updated the README and Slack runbook to show both the `.env.slack` configuration
  check and live worker command while keeping the ignored secret file out of Git.

### Verification

- `uv run pytest tests/python/test_documented_commands.py -q` passed (6 tests).
- `uv run python scripts/check_public_files.py` passed.
- `git diff --check -- README.md` passed.

## Slack preview decision controls

### Pilot result

- The first reported live confirmation-required `sold` batch completed end to end
  and committed 18 listing changes. Only this aggregate result is recorded; private
  screenshot rows and Slack identifiers remain local.
- This begins the controlled pilot but does not satisfy the 20-batch autonomy gate.

### Behavior

- Confirm and Reject now immediately replace the interactive preview buttons with a
  non-interactive decision state.
- The independently retried terminal receipt updates that same preview message rather
  than posting a second reply, so stale buttons cannot remain confusingly active.

### Verification

- Focused Slack worker and capture-repository verification passed (14 tests).
- `./scripts/check.sh` passed: Ruff lint and formatting, 325 Python tests, package
  compilation, dbt debug/parse, nine seed loads, all 126 dbt build nodes, SQLFluff,
  and public-file policy.
- `git diff --check` passed, and ignored private Slack configuration, evidence,
  operational databases, and backups remained outside the publication set.

## Recipe Calculator cost-banded default quantities

### Behavior

- New Recipe Calculator entries use a quantity of four below 50,000 kamas, three
  from 50,000 through below 100,000, two from 100,000 through 500,000, and one above
  500,000 or when current recipe cost is incomplete.
- The rule applies to calculator search and suggestions plus shared Add actions on
  Recipes, Best Sellers, Profit Opportunities, and item detail.
- Existing saved cart quantities remain unchanged. Out of Stock's explicit Suggested
  Restock quantity continues to take precedence over the cost-banded default.

### Verification

- Boundary coverage includes 0, 50,000, 100,000, and 500,000 kamas plus missing,
  negative, just-below, and just-above cases.
- Focused recipe, web, and static-asset verification passed (111 tests).
- `./scripts/check.sh` passed: Ruff lint and formatting, 334 Python tests, package
  compilation, dbt debug/parse, nine seed loads, all 126 dbt build nodes, SQLFluff,
  and public-file policy.

## Selected craft breakdown default order

### Behavior

- Selected craft rows default to Profession ascending, then Category ascending, then
  Craftable Item ascending.
- Uncategorized crafts use their displayed `Uncategorized` label for the category
  tie-breaker, and Profession remains the table's declared primary active sort.

### Verification

- Focused recipe and web verification passed (94 tests).
- `./scripts/check.sh` passed: Ruff lint and formatting, 335 Python tests, package
  compilation, dbt debug/parse, nine seed loads, all 126 dbt build nodes, SQLFluff,
  and public-file policy.

## Recipe required-level tier selectors

### Behavior

- Replaced the free numeric and dual-range Recipes controls with minimum and maximum
  selectors limited to the governed profession levels 1, 10, 20, 40, 60, 80, and
  100.
- Preserved the inclusive filter behavior and existing `min_level` and `max_level`
  query parameters while removing browser synchronization code and slider-only CSS.
- Added the discrete tiers directly beside the controls so impossible ranges such as
  50 through 59 are no longer presented as valid choices.

### Verification

- Focused recipe, web, and static-asset verification passed (111 tests).

## Best Sellers total profit

### Behavior

- Replaced Best Sellers' per-item Estimated Profit with Total Profit summed across
  completed Sales whose Cost at Sale is stored or historically reconstructable.
- Changed Top Profit to rank the same aggregate instead of current estimated unit
  margin, while retaining Estimated ROI as a separate current-economics measure.
- Clarified the page context so recorded historical measures and current estimates are
  distinguishable.

### Verification

- Focused Sales, Best Sellers web, and Insights verification passed (98 tests).
- The real ignored SQLite Best Sellers projection completed successfully in about 1.6
  seconds, including legacy historical-cost reconstruction.
- `./scripts/check.sh` passed: Ruff lint and formatting, 334 Python tests, package
  compilation, dbt debug/parse, nine seed loads, all 126 dbt build nodes, SQLFluff,
  and public-file policy.

## Simplified Sales Over Time

### Behavior

- Reduced Sales Over Time to three always-visible totals, chart lines, and daily-table
  columns: All Sales, All Cost, and All Profit.
- Decoupled the chart from the Sales table filters so it always represents every
  completed Sale, including when the visible table is filtered to active listings.
- Removed coverage-only KPIs and series switches. All Cost and All Profit continue to
  exclude completed Sales with unknown Cost at Sale rather than treating missing cost
  as zero.

### Verification

- Focused Sales, web, and static-asset verification passed (111 tests).

## Restored Recipe level range

### Behavior

- Restored the Recipes dual-handle required-profession-level range and synchronized
  numeric endpoints in place of the discrete selectors.
- Preserved the existing inclusive `min_level` and `max_level` query behavior and the
  endpoint-crossing guard while allowing category filters such as Belt to be combined
  with freely chosen numeric levels.

### Verification

- Focused recipe, web, and static-asset verification passed (111 tests).
- Real ignored-database smoke requests returned HTTP 200 for Belt-filtered Recipes
  with the range slider and active-filtered Sales with the all-history chart visible.
- `./scripts/check.sh` passed: Ruff lint and formatting, 334 Python tests, package
  compilation, dbt debug/parse, nine seed loads, all 126 dbt build nodes, SQLFluff,
  and public-file policy.

## Rich Slack sold receipts

### Behavior

- Replaced a committed `sold` capture's generic listing-change receipt with listings
  sold, total recorded sales revenue, total known cost, total known profit, and
  explicit cost coverage.
- Added the affected items that have no active listing after the capture and an
  aggregated count of screenshot rows excluded as out of scope.
- Kept missing cost snapshots out of both known cost and known profit instead of
  treating them as zero. Market and other capture receipts remain unchanged.
- Reused the existing capture audit relationships and saved validation plan, so no
  schema migration or additional Slack permission is required.

### Verification

- Focused Slack worker and capture-repository verification passed (15 tests).
- `./scripts/check.sh` passed: Ruff lint and formatting, 335 Python tests, package
  compilation, dbt debug/parse, nine seed loads, all 126 dbt build nodes, SQLFluff,
  and public-file policy.
- `git diff --check` passed before staging.

## Item Search editing and Price Priorities

### Behavior

- Made each Item Search Current Price cell directly editable. Enter or leaving a
  changed field appends an audited quantity-one price observation, preserves the
  search, filters, sort, and scroll position, and does not create a Sales listing.
- Added **Price Priorities** under the Item navigation. It lists items with missing
  prices and identifies the latest recipes whose complete profit calculation would be
  unlocked or advanced by pricing each item.
- Ranked missing items first by immediately unlocked recipe count, then completed
  Sales across those newly unlocked craftable items, affected recipe count, total
  completed Sales across affected recipes, and item name. Within each item, recipes
  needing no other prices appear before recipes with additional blockers.
- Treated both crafted-output and ingredient prices as full-profit blockers. Recipes
  with unresolved ingredient identities are excluded because adding a price cannot
  resolve their identity.
- Added inline ranked-page price entry, summary counts, client-side table sorting,
  validation feedback, empty-state handling, navigation state, and public README
  documentation.

### Verification

- Focused recipe, web, and static-asset verification passed (117 tests).
- `./scripts/check.sh` passed: Ruff lint and formatting, 341 Python tests, package
  compilation, dbt debug/parse, nine seed loads, all 126 dbt build nodes, SQLFluff,
  and public-file policy.
- `git diff --check` passed, and no secrets, private raw data, operational databases,
  warehouses, or observer files entered the change set.

## Combined Shopping List old-price highlight

### Behavior

- Added a light, theme-aware warning highlight to Combined Shopping List rows whose
  current ingredient price was observed 10 or more calendar days ago.
- Kept 9-day rows unhighlighted and left the existing 7-day **Stale price** status
  unchanged; the new threshold is a separate visual prompt to review the price.
- Documented the threshold in the public README.

### Verification

- Focused calculator and stylesheet verification passed, including the 9-day and
  10-day boundary (3 tests).
- `./scripts/check.sh` passed: Ruff lint and formatting, 343 Python tests, package
  compilation, dbt debug/parse, nine seed loads, all 126 dbt build nodes, SQLFluff,
  and public-file policy.
