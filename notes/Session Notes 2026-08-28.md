# Session Notes 2026-08-28

## Screenshot sales reconciliation

- Reviewed three private screenshots from outside the repository and found 50
  distinct visible sale messages after removing one visually confirmed overlap.
- Limited the reconciliation to items whose latest recipe profession was Tailor,
  Shoemaker, or Jeweller. This produced 31 qualifying individual-item sales and
  excluded 19 raw-material stack sales.
- Required exact active item-name and asking-price matches for every included
  occurrence. All 31 qualifying sales matched without repricing or fabricating
  listings; the oldest identical active listing was selected first.
- Applied the approved count-based allocation atomically: 22 sales on Pacific date
  2026-08-27 (70.97%) and 9 on 2026-08-28 (29.03%). Recorded revenue was 1,739,200
  kamas and 709,000 kamas, respectively.
- Stored recipe-cost-at-sale snapshots using observations available at the assigned
  timestamps. Twenty-two of the 31 sales had complete historical cost coverage.
- Active listings changed from 183 to 152 and completed listings from 122 to 153.
  The screenshots were not copied into the repository or its tracked notes.
- Created an ignored recovery backup at
  `data/app/backups/dofus_touch-before-screenshot-sales-backfill-20260828T174946Z.sqlite3`.
  No BigQuery snapshot was published.

## Same-day follow-up screenshot

- Reviewed one additional private screenshot containing 18 distinct sale messages.
  Eleven were qualifying Tailor, Shoemaker, or Jeweller items and seven were
  excluded raw-material sales.
- Every qualifying occurrence had an exact active item-name and asking-price match.
  Recorded all 11 atomically on Pacific date 2026-08-28 for 1,800,000 kamas of
  additional revenue; eight had complete historical recipe-cost coverage.
- Across both screenshot batches, 2026-08-28 received 20 qualifying sales totaling
  2,509,000 kamas. Active listings now total 141 and completed listings total 164.
- Created an ignored recovery backup at
  `data/app/backups/dofus_touch-before-today-screenshot-sales-20260829T045826Z.sqlite3`.
  The follow-up screenshot was not copied into the repository, and no BigQuery
  snapshot was published.

## Verification

- SQLite `PRAGMA integrity_check` returned `ok` for both the updated operational
  database and both recovery backups after their respective mutations.
- An independent reconciliation query confirmed that the screenshot batches now
  contain 22 rows on 2026-08-27 and 20 rows on 2026-08-28, with the expected revenue
  totals, and that every updated row's latest recipe profession was one of Tailor,
  Shoemaker, or Jeweller.
- The full application check suite was not run for the data-only screenshot
  mutations because application code, schemas, dependencies, and model behavior
  were unchanged; verification was scoped to operational data and tracked-note
  policy.

## Restock Candidates calculator toggle

- Made the Restock Candidates Recipe Calculator action an opt-in toggle within the
  shared cart script. `Add` still seeds Suggested Restock as Craft Quantity; after
  addition, the enabled `Added ✓` control removes the item from both browser-local
  cart membership and calculator selection and then restores `Add`.
- Kept the toggle scoped to Restock Candidates. Other pages using the shared cart
  script retain their existing disabled `Added ✓` behavior.
- Added `aria-pressed` state plus action-specific add and remove accessible labels.
- Added template and static-script regression coverage for the opt-in toggle,
  removal behavior, Suggested Restock quantity, and accessible state.

### Verification

- Focused static-asset and Out of Stock web tests passed: 19 tests with the existing
  Starlette `TemplateResponse` deprecation warning.
- `./scripts/check.sh` passed: 255 Python tests, Python lint and formatting, package
  compilation, dbt profile validation and parsing, SQL lint, and public-file policy.
  The Python suite retains the same existing Starlette deprecation warning.

## Combined Shopping List craftable-item column

- Changed the Combined Shopping List grain to one unique craftable-item/ingredient
  pair per row. Repeated slots for the same ingredient in one recipe consolidate,
  while ingredients shared across crafts split into per-craft quantities without a
  comma-separated multi-craft cell.
- Made the first `Craftable Item` cell an image-backed link to item detail. Rows
  default to craft name ascending, then ingredient name ascending, while retaining
  typed sorting on every displayed column.
- Kept Unique Ingredients, Price Coverage, overall cost, and overall weight based on
  unique ingredient identity or summed requirements as appropriate, so split rows
  do not inflate summary coverage or change shopping totals.
- Gave repeated inline price forms for a shared market ingredient unique DOM input
  identifiers while retaining the same append-only price update and recalculation.
- Versioned the session-storage sort key because saved shopping-list sorting uses a
  column index. This discards a pre-change index once and then preserves sorting
  across price recalculations using the new column order.
- Updated service, web, and static-asset regressions for per-craft quantities,
  repeated-slot consolidation, alphabetical order, images, links, summary totals,
  unique input identifiers, and the sort-state key.

### Verification

- Focused Recipe Calculator and static-asset tests passed: 20 tests with the existing
  Starlette deprecation warning.
- `./scripts/check.sh` passed: 255 Python tests, Python lint and formatting, package
  compilation, dbt profile validation and parsing, SQL lint, and public-file policy.
  The Python suite retains the same existing Starlette deprecation warning.

## Selected craft breakdown default order

- Changed the server-rendered Selected craft breakdown to default to Profession
  ascending, with craft name ascending as the deterministic tie-breaker.
- Marked the Profession header as the active ascending sort for accessible and
  visible agreement with the rendered row order.
- Kept the Combined Shopping List's independent craft-name ordering unchanged.
- Updated service and web regressions for the new row order and active header.

### Verification

- Focused service and web tests passed: 2 tests with the existing Starlette
  deprecation warning.
- `./scripts/check.sh` passed: 255 Python tests, Python lint and formatting, package
  compilation, dbt profile validation and parsing, SQL lint, and public-file policy.
  The Python suite retains the same existing Starlette deprecation warning.
