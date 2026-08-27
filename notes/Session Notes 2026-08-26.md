# Session Notes 2026-08-26

## Sales Over Time cost-coverage presentation

- Clarified that All Sales includes every priced completed listing, including sales
  whose sale-time recipe cost is unknown.
- Added Cost-Covered Sales and aligned Covered Cost and Known Profit to the same
  population, making the displayed relationship `Known Profit = Cost-Covered Sales
  - Covered Cost` explicit.
- Updated the KPI strip, chart legend, accessible chart description, explanatory
  note, and daily table with scope-specific labels.
- Added regression coverage for a day where high uncovered sales make All Sales
  exceed Covered Cost while Known Profit remains negative.

## Verification

- `./scripts/check.sh` passed: 254 Python tests, Python lint and formatting, package
  compilation, dbt profile validation and parsing, SQL lint, and public-file policy.
- The Python suite retains one existing Starlette `TemplateResponse` deprecation
  warning.

## Active listing duplicate cleanup

- Found three identical batches of three active listings for Black Rat Boots,
  Gorgoyle Boots, and Black Rat Belt.
- Preserved the earliest batch for each item and deleted the two later duplicate
  batches: 18 active rows total. The duplicates were not marked as sales.
- Created an ignored recovery backup at
  `data/app/backups/dofus_touch-before-duplicate-listing-cleanup-20260827T053751Z.sqlite3`.
- Verified that each requested item has exactly three active listings after cleanup.

## Recipes availability filter

- Added a "Show only items not currently selling" checkbox to the Recipes filter
  form. It is opt-in, so the default catalog remains unchanged.
- Threaded the filter through recipe query parsing, URL state, catalog filtering,
  sorting, paging, and inline price-update redirects.
- Added service and web regression coverage for excluding actively listed items,
  rendering the checked state, and preserving the selection after a price update.
- `./scripts/check.sh` passed with 254 Python tests plus lint, formatting, package
  compilation, dbt profile validation and parsing, SQL lint, and public-file policy.
