# Session Notes 2026-09-05

## Download screenshot sales reconciliation

- The user's Downloads path maps to `/mnt/c/Users/jwtre/Downloads/` in this
  environment. Inspected `IMG_9227.png` and `IMG_9228.png` outside the repository.
- Transcribed 49 complete sold notifications. No matching boundary sequence
  established screenshot overlap; retained repeated sales and excluded clipped text.
- Used each image's local save time, approximately 2026-09-05 19:54:01 Pacific,
  following the established screenshot reconciliation convention.
- The deterministic planner matched 34 occurrences to active exact-name listings
  within Tailor, Shoemaker, and Jeweller. Reserved exact-price matches first and
  selected oldest listings deterministically.
- Left 15 occurrences unchanged. Fourteen were non-craftable or outside approved
  professions. Sapphire matched three catalog identities; inspected all three and
  established that each had no recipe or a Miner recipe. Retained that ambiguity
  in the ignored report and excluded the row without choosing an identity.
- Created an integrity-checked online backup before one transaction marked all 34
  listings sold with manual lineage and recipe-cost snapshots. Corrected one
  Whitepaw Wabbit Bracelet from 59,000 to 60,000 kamas through the Sales service,
  appending its linked price observation.
- Recorded 2,514,000 kamas revenue, 1,860,677 kamas recipe cost, and 653,323 kamas
  realized profit, with cost coverage for all 34 sales. Active listings changed
  from 342 to 308; sold listings changed from 367 to 401.
- Private report: `data/reports/manual-screenshot-sales-2026-09-05.json`.
  Recovery backup:
  `data/app/backups/dofus-touch-before-manual-screenshot-sales-2026-09-05-20260906T025633805280Z.sqlite3`.
- Verified every selected timestamp, price, and manual sale lineage after commit.
  An independent comparison with the backup found exactly 34 existing listing
  rows changed, no listings added or deleted, and one price observation appended.
  Live and backup SQLite integrity checks passed; no foreign-key violations were
  found. The Sales page returned HTTP 200 through the application test client.
- No application code, schema, dependency, or analytical model changed, so the
  full check script was not run. Screenshots remain outside the repository and
  operational data, report, and backup remain ignored.
