# Session Notes 2026-08-30

## Manual sales recorded for August 29

### Request and resolution

- The user explicitly requested one completed sale each for Aerdala Wedding Ring,
  Royal Morello Cherry Amublop, and Ancestral Shin Guards for yesterday, interpreted
  as the Pacific calendar date 2026-08-29.
- All three names resolved exactly to verified catalog items. Aerdala Wedding Ring
  and Ancestral Shin Guards each had two identical active listings, so one occurrence
  per requested name was selected oldest-first, with listing ID breaking the tied
  Ancestral timestamps.
- Because no sale time was supplied and Ancestral Shin Guards was listed late that
  day, the shared effective timestamp is 2026-08-29 23:59:59 America/Los_Angeles
  (2026-08-30 06:59:59 UTC). This preserves the requested date without placing a sale
  before its listing start.

### Operational update

- Created and integrity-checked ignored online backup
  `data/app/backups/dofus-touch-before-manual-sales-20260830T164835Z.sqlite3`.
- Atomically marked the selected 23,000-kama Aerdala Wedding Ring, 84,000-kama Royal
  Morello Cherry Amublop, and 168,000-kama Ancestral Shin Guards listings sold through
  the governed Sales service with manual provenance.
- Historical recipe cost was unavailable for all three at the assigned timestamp,
  so `recipe_cost_at_sale` and realized profit remain null rather than assuming zero.
- One active Aerdala Wedding Ring and one active Ancestral Shin Guards remain. Royal
  Morello Cherry Amublop now has no active listing.

### Verification

- Confirmed exactly three selected listings have the requested Pacific sale date and
  manual sale source.
- SQLite integrity remained `ok`, and the live `/sales` endpoint returned HTTP 200.
- No tracked application code, private raw export, analytical snapshot, or hosted
  BigQuery/dbt state changed.

## BigQuery recipe-economics assertion fix

### Diagnosis and correction

- The hosted `assert_recipe_economics_consistent` failure returned exactly 130 rows.
  Replaying BigQuery's nine-decimal `NUMERIC` division against the current local
  operational values reproduced exactly 130 failures, confirming that recipe costs,
  profits, and ROI values were correct.
- The assertion multiplied the rounded ROI by recipe cost and required the original
  profit to be reconstructed within `0.000001` kama. The rounding residual scales
  with recipe cost, so valid hosted rows exceeded that fixed tolerance.
- Replaced the inverse multiplication check with direct comparison to the existing
  adapter-dispatched `divide_whole_amount(estimated_profit, recipe_cost)` formula.
  This continues to enforce the governed `ROI = profit / recipe cost` definition on
  both DuckDB and BigQuery without weakening it through a wider arbitrary tolerance.

### Verification

- Focused seed/build verification passed all nine seeds and all 126 dbt nodes; the
  corrected singular assertion passed, and its SQLFluff lint passed.
- `./scripts/check.sh` passed: Ruff lint/formatting, 324 Python tests, package
  compilation, dbt debug/parse, nine seed loads, all 126 dbt build nodes, SQLFluff,
  and public-file policy.
- The 03:51 hosted rerun returned the same 130 failures because GitHub `main` still
  pointed to `71255ef` and therefore still contained the original assertion. Pushed
  the atomic fix commit `ca1cbb3` to `origin/main` and confirmed the remote test now
  contains the adapter-dispatched comparison.
- A BigQuery-precision replay across all 137 eligible current operational rows
  returned 130 failures for the old predicate and zero for the published predicate.
  No hosted BigQuery build was triggered from the local environment; rerun the job
  against `ca1cbb3` or later.

## Combined Shopping List view-preservation fix

### Diagnosis and correction

- Updating a Current Unit Price already saved the Combined Shopping List sort state
  and scroll offset before recalculating the page, but restoration assumed every
  column began unsorted. The server marks Craftable Item ascending by default, so
  unconditional restore clicks could reverse that order instead of preserving it.
- Sort restoration now compares the rendered header direction with the saved
  direction. It leaves an already matching order untouched and clicks only until an
  unsorted or oppositely sorted column reaches the requested direction.

### Verification

- The static-asset regression and Recipe Calculator integration test passed.
- `./scripts/check.sh` passed: Ruff lint/formatting, 324 Python tests, package
  compilation, dbt debug/parse, nine seed loads, all 126 dbt build nodes, SQLFluff,
  and public-file policy.
