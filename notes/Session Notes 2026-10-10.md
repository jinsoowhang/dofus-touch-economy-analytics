# Session Notes 2026-10-10

## Weekday sales catch-up and reusable skill

- The user requested reconciling new Downloads sale screenshots since their last
  report, spreading the sales proportionally across missed days according to weekday
  trends, and creating a reusable skill for this workflow.
- Reviewed memory, the October 4/5 session notes, operational source/architecture
  constraints, and previous private audits. The task-observer skill was unavailable;
  no observer logs were created. Preserved the preexisting memory changes and
  untracked October 5 session note.
- Visually transcribed 21 complete quantity-one sales in `IMG_9539.png` and 23 in
  `IMG_9540.png`. Enlarged one line to confirm the exact spelling Amufafah after the
  initial transcription failed exact catalog matching. All 44 final names resolve
  uniquely within the approved Tailor/Shoemaker/Jeweller scope, with enough active
  exact-price listings. Repeated identical notifications remain separate occurrences;
  the screenshot boundaries do not establish a duplicate scroll sequence. Three
  unidentified expiration notices and a clipped unreadable fragment caused no changes.
- Used the committed October 5 screenshot report as the coverage checkpoint and the
  established save-time date convention for the new October 10 images. The reporting
  interval is October 6–10 Pacific, inclusive, under the user's request to catch up
  since their last report and their prior approval of the interval convention.
  Unrelated manual sales are not reporting checkpoints and remain unchanged.
- Reconstructed the complete August 22–September 12 baseline from non-estimated
  SQLite sales and verified exact agreement with the prior audit: 634 sales across
  22 complete daily-check dates. Weekday means correct unequal exposure; estimates
  and the partial first day are excluded. This small baseline is provisional and
  sensitive to inventory and recording behavior.

| Assigned Pacific date | Sales | Actual revenue allocated (kamas) |
| --- | ---: | ---: |
| 2026-10-06 | 8 | 391,000 |
| 2026-10-07 | 9 | 265,000 |
| 2026-10-08 | 10 | 460,000 |
| 2026-10-09 | 7 | 397,000 |
| 2026-10-10 | 10 | 518,000 |
| Total | 44 | 2,031,000 |

- Largest-remainder rounding preserves whole sales; notification order maps to
  chronological date slots. All 44 assigned dates carry `manual_estimated_date`
  lineage. Actual per-sale screenshot prices remain intact, with no corrections.
  Earlier dates use 23:59:59 Pacific and October 10 is capped at the evidence save
  time. All selected listing starts precede their assignments. Historical recipe
  costs are known for every sale, but date-dependent cost/profit and timing metrics
  also depend on the estimated dates. Current charts show assigned dates without
  estimate badges.
- Created an integrity-checked online SQLite backup and rehearsed on an isolated
  copy. Revalidated live state and evidence under a write lock, then marked the
  complete batch sold through `SalesService` in one transaction. Before/after and
  saved-state checks prove exactly 44 existing listings changed, zero observations
  appended, no listings created/deleted, original starts preserved, prior observations
  and unrelated tables unchanged, conserved revenue, and passing integrity/foreign-key
  checks. Live counts changed from 732 sold/230 active to 776 sold/186 active.
- The live transaction and saved-state checks succeeded, but final comparison against
  the JSON rehearsal audit initially compared tuple counts with list counts. Fixed
  the private driver to return JSON-compatible lists and finalized the audit using
  read-only saved-state verification against the original backup. Verified identical
  trial/live listing results; did not replay the transaction. The committed private
  audit records the recovery and remains the replay checkpoint.
- Evidence, transcripts, inputs, allocation output, drivers, rehearsal database,
  and backup stay in ignored local paths. The audit is
  `data/reports/manual-screenshot-sales-2026-10-10.json`.
- Created discoverable repository skill
  `.agents/skills/dofus-sales-catch-up/SKILL.md`, with focused operational reference,
  UI metadata, and a deterministic planning helper. Invoke as `$dofus-sales-catch-up`.
  Installed a user-directory symlink at `~/.codex/skills/dofus-sales-catch-up` to
  the repository skill so both discovery paths use the same maintained files.
  It preserves reporting coverage/evidence, exact matches, price totals, temporal
  bounds, estimated lineage, and local atomic-write ownership. It never expands
  Slack pilot autonomy or publishes data. Its helper has no database access.
- Verification passed: skill validation; 56 focused allocation/Sales/capture tests;
  helper CLI execution matching the committed allocation; repository and explicit
  skill lint/formatting; private-driver lint/formatting; public-file policy; and
  working-tree whitespace. The helper tests cover conservation, unequal weekday
  exposure, verified zero days, deterministic rounding, single-day lineage, empty
  batches, insufficient training, invalid dates/prices, duplicate listings, and
  listing-start bounds. Home, Sales, Dashboard, and Insights each returned HTTP 200
  against the running local web server.
- The full `scripts/check.sh` was not run: application code/schema/dependencies and
  dbt models were unchanged; the new skill/helper and local data mutation received
  focused verification. No Git staging, commit, push, Slack message, or BigQuery
  publication was performed.
- Explained opening the Web UI: run `uv run dofus-web` from the project directory,
  keep the terminal open, and browse `http://127.0.0.1:8000`.
