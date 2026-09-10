# Session Notes 2026-09-09

## Dated Downloads screenshot sales

- Inspected all five screenshots from the Windows-mounted Downloads folder:
  two marked September 8 and three marked September 9, 2026. The supplied host
  path resolves here through `/mnt/c/Users/jwtre/Downloads`.
- Followed the established exact-name and latest-recipe profession scope for
  Tailor, Shoemaker, and Jeweller. Matched 51 active listings at exact screenshot
  prices; no price corrections or new listings were needed. Repeated equipment
  notifications were separate sales. Kido Rear Feather, Nelween Essence, and
  overlapping/clipped Dragomilk notifications remained outside scope.
- Filename dates control the Pacific sale date. September 8 uses 23:59:59 Pacific;
  September 9 uses each screenshot's save time. Stored timestamps are UTC.
- Created an integrity-checked online SQLite backup and revalidated the complete
  plan under a write lock. Recorded all 51 sales atomically through SalesService
  with manual lineage and historical cost snapshots. Seven costs remain unknown.
- Recorded 23 sales totaling 1,121,900 kamas for September 8 and 28 totaling
  2,584,000 kamas for September 9: 3,705,900 kamas overall. Active listings decreased
  from 380 to 329; sold listings increased from 532 to 583.
- Compared every application table against the backup: exactly the selected 51
  listing rows changed, with no additions or deletions, and all other tables were
  unchanged. Verified prices, timestamps, and manual lineage; SQLite integrity and
  foreign-key checks passed. The private report records evidence hashes, source
  quantities, date assignments, listing IDs, costs, and the backup path at
  `data/reports/manual-screenshot-sales-2026-09-09.json`.
- The Sales page rendered HTTP 200 through the application test client. The
  public-file policy and working-tree whitespace checks passed.
- No application code, schema, dependencies, or analytical models changed. The
  full check script was not run for this local data-only operation. Screenshots,
  operational data, scripts, reports, and backups remain outside tracked files.
- Preserved the pre-existing MEMORY.md changes and September 7 session note.
