# Session Notes 2026-10-04

## Screenshot sales catch-up preparation

- Resolved the user-supplied host Downloads path through the available Windows
  mount. Reviewed all twelve new screenshots labeled MMDDYYYY, covering September
  10–12, 14, 18–20, 26, and October 4. September 8–9 notifications were already
  committed: four screenshots match prior evidence hashes, and the re-saved third
  September 9 screenshot was visually checked against the prior transcript.
- Retained the established exact-name, latest-recipe Tailor/Shoemaker/Jeweller
  scope. Prepared 124 matched sales totaling 8,293,900 kamas. Twelve resource
  notifications are outside scope. Five existing listing prices need corrections
  to the visible screenshot prices. No missing listings or identities were guessed.
- Confirmed the September 10 scroll boundary: the clipped bottom notification in
  the first image becomes the first complete notification in the second image;
  the clipped top notification in the second image overlaps the final complete
  notification in the first. Three distinct Jules notifications remain overall.
- Prepared weekday weights from 634 sales across 22 daily-check dates, August 22
  through September 12, excluding the first partial operational date. Used mean
  sales per observed weekday to correct unequal weekday exposure. Monday has the
  largest fitted weight; only three to four observations support each weekday, so
  the weights are provisional and affected by inventory and recording behavior.
- Asked whether every later dated screenshot contains all sales since the preceding
  dated login, with no missing logins. This material interval clarification was
  pending during preparation and subsequently approved below. Intervals start the
  next calendar day and include the labeled date. Largest-remainder rounding preserves whole sales and actual batch totals;
  notification order maps items to chronological date slots.
- Multi-day batches contain 51 sales with proposed `manual_estimated_date` lineage;
  the other 73 use `manual`. Original screenshot dates, hashes, rows, prices, listing
  identities, weights, and allocation rules are retained in the ignored audit.
  Existing website charts display assigned dates without an estimate badge. Later
  weekday analysis must exclude imputed dates. Unidentified expiration messages
  are not sales and do not justify removing active listings.
- The ignored `data/reports/manual-screenshot-sales-2026-10-04.json` contains the
  complete plan and trial verification. The accompanying readable review is
  `data/reports/sales-catch-up-2026-10-04.md`. Reconciliation and commit scripts also
  remain ignored. Live SQLite is unchanged at 583 sold and 329 active listings.
- Applied the plan to an isolated SQLite copy: exactly 124 listings changed, five
  observations appended, existing observations and unrelated tables unchanged.
  The copy has 707 sold and 205 active listings; ten new sales have unknown costs.
  Integrity and foreign-key checks passed. Home, Sales, Dashboard, and Insights
  rendered HTTP 200 on the copy. The commit script repeats table-level verification
  before committing, requires the interval clarification, and backs up live SQLite.
- Scoped verification passed: 42 Sales and capture-service tests, lint/formatting
  of the private scripts, public-file policy, and working-tree whitespace. The full
  check script was not run because this is local data reconciliation with no changes
  to application code, schema, dependencies, or analytical models.

## Approved sales catch-up applied

- The user instructed: "go ahead with your recommendation." Recorded that approval
  in the private audit and applied the prepared login intervals and weekday weights.
- Created an integrity-checked online SQLite backup, then revalidated evidence,
  listing matches, prices, weekday analysis, and allocations under a write lock.
  Marked all 124 listings sold atomically through SalesService, preserving actual
  batch revenue of 8,293,900 kamas and historical recipe-cost snapshots. Fifty-one
  multi-day date assignments have `manual_estimated_date` lineage; 73 single-day
  assignments have `manual` lineage. Ten costs remain unknown.
- Verified the transaction before commit and again against the saved live database:
  exactly 124 listing rows changed, exactly five price observations were appended,
  existing observations and all unrelated tables were unchanged. No listings were
  created or deleted. Sale prices, assigned dates, lineage, and listing-start bounds
  match the plan. SQLite integrity and foreign-key checks passed.
- Live counts are now 707 sold and 205 active. Home, Sales, Dashboard, and Insights
  each returned HTTP 200 against live SQLite. Updated both private reports to
  committed status with the backup location, saved daily totals, and verification.
  Do not replay this batch.
- Reused the successful 42 scoped tests from preparation because no application code
  changed. The full check script remains unnecessary for this local data operation.
  Public-file policy and working-tree whitespace checks were repeated. Operational
  data, reports, scripts, and backups remain ignored; only memory and session notes
  are working-tree changes.
