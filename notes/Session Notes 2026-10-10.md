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

## Ingredients to Buy ordering

- The user requested Ingredients to Buy ordered by Profession, Craftable Item,
  then each item's ingredient order from the item page.
- Added profession to calculator ingredient rows and their accumulators, then
  sorted by profession/name/source position. Added the sortable Profession column
  before Craftable Item and Ingredient, with the primary ascending state exposed.
  Existing source position, first-slot consolidation, shared ingredient quantities,
  costs, weights, price updates, and selected-craft breakdown ordering are preserved.
- Advanced transient shopping-list sort storage to v3 and versioned the calculator
  script so old column indices do not restore an incorrect sort. Profession and
  Craftable Item retain original-row tie-breaking after another column sort.
- Regression coverage checks cross-profession ordering, name ordering within a
  profession, and ingredient sequence against item detail, including consolidated
  repeated slots. Recipe/static checks and real Chromium verification passed,
  including stale v2 sort-state rejection and descending profession sort retention
  after an ingredient-price update. Quantities, costs, weights, and price-update
  behavior remain intact. No schema or dependency change was needed.
- Before publication, exported the ingredient-only staged tree and verified it
  independently: all 135 recipe/static/web tests passed against that tree's source,
  without the later chart changes. The temporary export was removed.

## Sales Over Time ranges

- The user requested Sales Over Time opening on the last seven days with
  14/30/60/90-day and historical choices.
- Added URL-backed Sales Over Time links for Last 7 days (default), Last 14 days,
  Last 30 days, Last 60 days, Last 90 days, and Historical. Finite periods use Pacific
  calendar dates, including today plus the preceding N−1 days, with all dates
  represented and future activity excluded. Historical retains the existing complete
  recorded history. Chart totals and Daily Totals follow the period; Today cards
  retain their current-day/inventory meaning. Missing actual sale costs stay unknown.
  Empty periods retain all range controls and explain how to show earlier activity.
- The range travels in the existing Sales page state, preserving it through table
  filtering, clear filters, sorting, both paginations, and mutation redirects. Range
  links preserve existing table state. Table filters remain independent of the chart.
  No schema/dependency changes or live operational data writes were needed.
- Nine new HTTP cases cover every chart range and the default,
  Pacific date boundaries, inclusive calendar lengths, selected totals, current-day
  losses, empty periods, input validation, and retained filter/sort/page/mutation state.
  Existing all-history chart tests now explicitly request Historical.
- Chromium verification on an isolated synthetic database passed all six range
  controls, default profession/craft/recipe order, stale v2 sort-state rejection,
  sorting by ingredient then restoring Profession, and descending profession sort
  retention after an actual ingredient-price update and recalculation. No JavaScript
  errors occurred. The synthetic server/database were removed; the ignored driver
  remains `data/reports/verify-ui-ranges-and-order-2026-10-10.py`. The browser used
  existing cached Chromium and NSS libraries through a transient uv environment.
- The complete `./scripts/check.sh` passed: Python lint/formatting, all 448 Python
  tests, package compilation, dbt debug/parse/seed/build (126 successful build
  nodes), SQL lint, and public-file policy. JavaScript syntax and working-tree
  whitespace checks also passed. Existing unrelated session changes remain intact.
- Stop the running web command with Ctrl+C, restart `uv run dofus-web`, and refresh
  the browser to load the new server behavior and versioned calculator script.
  No migration is needed. No Git staging, commit, or publication was performed.

## Sales Over Time point hover details

- The user requested point data when hovering over Sales Over Time. Previously the
  circles only exposed native SVG titles. Added an immediate visible tooltip beside
  the pointer containing series, Pacific date, comma-grouped kamas, and included
  item count. Cost/profit descriptions identify sales with known cost at sale.
- Points are keyboard-focusable with accessible data labels and focus outlines;
  focus and tap also show details. Pointer exit, blur, Escape, and chart series
  toggles dismiss the tooltip. Hidden series cannot show stale point details.
  Native SVG titles remain a no-JavaScript fallback. SVG group semantics expose
  the individually labeled points. No chart calculations or operational data changed.
- Added theme-aware fixed tooltip styling and viewport placement. Browser testing
  caught shrink-to-fit width changing after narrow-screen positioning; explicit
  max-content width with the existing viewport maximum fixed it. The final browser
  check passes on both desktop and a 500px-wide viewport. Versioned Sales JavaScript
  and the stylesheet to load the updated assets on refresh.
- Verification passed: 108 focused web/static/range tests, repository Python
  lint/formatting, Sales JavaScript syntax, public-file policy, and working-tree
  whitespace. HTTP coverage verifies generated tooltip data, negative profit,
  accessible point markup, and updated asset loading. Chromium checked real pointer
  hover and keyboard focus across all four series, exact tooltip text, negative
  amounts, pointer exit, Escape, hidden-series dismissal, and viewport bounds.
  Existing calculator ordering, price-edit restoration, and all six chart ranges
  also passed in that browser run, with no JavaScript errors.
- Browser writes were limited to a temporary synthetic database, which was removed
  with its server. The ignored diagnostic remains
  `data/reports/verify-ui-ranges-and-order-2026-10-10.py`. Live SQLite was not written.
  The full check script was not repeated for this HTML/CSS/JavaScript-only change;
  its earlier successful 448-test/dbt/SQL run covers the unchanged Python application
  and analytical models. No staging, commit, or publication was performed.
- Refresh the Sales page to load the tooltip and versioned assets. This change
  requires no migration or Python server restart.

## Remove Pacific Time display labels

- Removed timezone wording from the Sales page's chart header, selected-period
  note, Today note, chart description, date axis, hover/accessibility descriptions,
  and date-filter help, following the user's request. Date grouping and range
  boundaries still use the existing `America/Los_Angeles` timezone; timestamps,
  chart amounts, and sales data were not modified.
- Updated the existing render assertions to verify the shorter tooltip text and
  absence of Pacific wording while retaining calendar-boundary and summary checks.
  Verification passed: 14 focused Sales chart/date/summary HTTP tests, focused
  Python lint/formatting, and working-tree whitespace. The full check script and
  browser run were not repeated for this text-only template change; calculation
  code, JavaScript interaction, and CSS remained as previously verified.
- Refresh Sales to see the new labels. No restart, migration, operational data
  write, staging, commit, or publication was needed.

## Listed gaps and tooltip rows

- The user requested blank Listed chart gaps on days without listings and separate
  tooltip rows for individual data fields. Listed now closes its current line
  segment when a day has no priced listing activity, or when consecutive plotted
  dates are separated by an unrecorded calendar day. This covers finite padded
  periods and sparse Historical activity. Adjacent listing dates still connect;
  isolated listing dates retain their point. Totals and other series keep their
  previous calculation and connection rules.
- Tooltips use labeled definition-list rows: Date, the selected series amount in
  kamas, and Count. Cost/Profit add a Coverage row for known cost at sale. Each
  point supplies structured, escaped attributes; JavaScript fills text content
  without parsing the accessible sentence or injecting HTML. Existing hover/focus,
  tap, dismissal, and viewport placement remain intact. Updated asset versions.
- Verification passed: 110 focused chart/web/static tests, repository Python
  lint/formatting, Sales JavaScript syntax, public-file policy, and working-tree
  whitespace. New tests cover both missing daily records and sales-only days in
  seven-day and historical windows, while checking preserved totals and other
  series connections. Chromium verified actual blank Listed segments across all
  ranges, row text and vertically separate row geometry, known-cost coverage,
  negative profit, hover/focus, dismissal, hidden series, and narrow viewport bounds.
  Existing calculator sorting and price-reload behavior also passed. No JavaScript
  errors; the synthetic database and server were removed.
- The full dbt/SQL check sequence was not repeated for this scoped chart
  presentation change; no persistence, schema, dependency, or analytical model
  changed, and those checks passed earlier in this session. Live SQLite was not
  written. No staging, commit, or publication was performed.
- Restart `uv run dofus-web` and refresh Sales to load the Python line-segmentation
  change and updated tooltip assets. No migration is needed.

## GitHub publication

- The user explicitly requested committing and pushing the pending session work.
  Used the github-to-local-repo fetch-first workflow to check `origin/main` at
  `jinsoowhang/dofus-touch-economy-analytics`. Its fetched tip matched the starting
  local `main` tip, `bcbaae3882b5dfb49ab6825be72948e4683dafec`, so no upstream
  integration or history rewrite was required.
- Prepared four atomic commit groups with their associated memory/session records:
  `495b166` records the prior October 5 sales and recipe refresh; `ce6f273` adds the
  weekday-weighted catch-up skill and tests; `37f2631` adds profession/craft/recipe
  ordering; the final Sales chart commit adds range selection, point details,
  timezone-label cleanup, Listed gaps, and this publication record.
- Staged explicit paths and partial file contents to keep the groups independent.
  Verified the ingredient commit's staged source separately in a temporary export:
  all 135 recipe/static/web tests passed before including the later chart changes.
  Kept the final working files intact while preparing each index snapshot.
- Reran the complete `./scripts/check.sh` against the final source: Python
  lint/formatting, all 450 Python tests, package compilation, dbt debug/parse/seed,
  all 126 build/test nodes, SQL lint, and public-file policy passed. Skill validation,
  explicit skill lint/formatting, both changed JavaScript syntax checks, and working
  plus staged whitespace checks also passed. Reused the successful browser checks
  because source and assets did not change during commit preparation.
- Publication targets `origin/main` through a normal fast-forward push. Screenshots,
  raw exports, SQLite/DuckDB databases, private reports/drivers, backups, and the
  user-directory skill link remain outside Git. The ignored confirmation report
  `data/reports/github-publication-2026-10-10/push-result.json` records the final
  commit IDs and remote confirmation after the push.
