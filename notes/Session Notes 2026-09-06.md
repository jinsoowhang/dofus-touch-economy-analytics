# Session Notes 2026-09-06

## Download screenshot sales reconciliation

- The user requested all sale records in Downloads. Inspected `IMG_9229.png` and
  `IMG_9230.png` outside the repository and transcribed 35 complete notifications.
  These are distinct login receipts; retained every repeated sale occurrence.
- Applied the established exact-name, latest-recipe profession scope and
  oldest-exact-price-first planner. All identities resolved without ambiguity after
  visually correcting the transcription of Sausshied. Matched 26 active listings;
  nine notifications were non-craftable or outside Tailor, Shoemaker, and Jeweller.
- Used each screenshot's save time, approximately 2026-09-06 17:58:23 Pacific,
  following the established convention. Created an integrity-checked online backup
  before revalidating the plan under a SQLite write lock and applying one transaction.
- Marked all 26 listings sold with manual lineage; corrected one Jellicape price
  from 57,000 to 56,000 through the Sales service and its append-only observation.
  Recorded 1,946,000 kamas revenue, 1,389,130 known recipe cost, and 531,870 known
  profit. Cost coverage is 25 of 26; Mad Boowolf Cloak cost remains unknown.
- Active listings changed from 379 to 353 and sold listings from 413 to 439.
  The ignored report retains source hashes, observed quantities, original plan,
  committed listing identifiers, timestamps, cost snapshots, and backup location:
  `data/reports/manual-screenshot-sales-2026-09-06.json`.
- An independent comparison to the backup confirmed exactly 26 existing listing
  rows changed, one price observation appended, no listing additions or deletions,
  and all other tables unchanged. Every selected price, timestamp, cost (including
  null), and manual lineage matched the report. SQLite integrity and foreign-key
  checks passed. A verification assertion initially failed on the legitimately null
  cost; corrected the read-only assertion and reran verification without any further
  operational writes.
- No application code, schema, dependency, or analytical model changed, so the full
  check script was not run. Operational data, screenshots, report, and backup remain
  ignored or outside the repository.
- The Sales page returned HTTP 200 through the application test client. The
  public-file policy and `git diff --check` passed; Git status contains only MEMORY
  and this session note.
