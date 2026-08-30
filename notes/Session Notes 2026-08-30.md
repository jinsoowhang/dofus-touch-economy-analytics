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
