# Session Notes 2026-09-07

## Downloads screenshot sales reconciliation

- Resolved the supplied host Downloads path to the equivalent Windows-mounted
  Downloads folder. Inspected five screenshots outside the repository: IMG_9231,
  IMG_9232, IMG_9233, IMG_9234, and IMG_9236.
- Transcribed 65 distinct complete notifications after removing the first Mature
  Smoke notification in IMG_9232, which overlaps IMG_9231. The clipped Mature Ashes
  notification also overlaps; repeated sales elsewhere were retained.
- The established exact-name and latest-recipe scope matched 57 active listings
  for Tailor, Shoemaker, and Jeweller, all at their recorded prices. Seven resource
  or Staff Carver notifications were outside scope. Hairy Cloak matched two catalog
  identities; requested confirmation for the sole active Ceremonial Cape listing
  at 17,000 kamas and left it unchanged pending the answer.
- Created an integrity-checked online SQLite backup, revalidated the plan under
  a write lock, and marked the 57 unambiguous listings sold in one transaction
  through SalesService with manual lineage and historical recipe-cost snapshots.
  Used each screenshot's save time, approximately September 7 at 20:41 Pacific,
  following the established convention.
- Revenue recorded: 3,512,000 kamas. Active listings changed from 414 to 357;
  sold listings changed from 471 to 528. No price corrections were needed.
- The ignored `data/reports/manual-screenshot-sales-2026-09-07.json` records image
  hashes, quantities, overlap treatment, timestamps, the plan, committed UUIDs,
  recipe-cost snapshots, backup location, pending identity, and verification.
- Compared every application table with the backup: exactly the selected 57
  listing rows changed, no listings were added or deleted, and all other tables
  were unchanged. Verified each sale price, timestamp, nullable cost, and manual
  lineage. SQLite integrity and foreign-key checks passed. Sales rendered HTTP 200
  through the application test client; the public-file policy passed.
- No application code, schema, dependencies, or analytical models changed, so the
  full check script was not run. Operational data and backups remain ignored;
  screenshots remain outside the repository.
