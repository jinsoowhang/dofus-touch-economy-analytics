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

## Sales Over Time summary rows

- Added Total Listed, Total Sales, Total Cost, and Total Profit as the first row
  and the corresponding Current cards directly below it. The Sales chart summary
  uses four desktop columns while retaining the existing small-screen stacking.
- Asked what Current should mean and recommended today's activity. With no answer
  received during implementation, proceeded with that stated assumption and
  displayed the exact Pacific calendar date above the second row.
- Reused the existing daily totals so Current follows the same listing-date,
  sold-date, historical-cost, and missing-cost rules as the chart. Both rows remain
  independent of Sales table filters; days without activity show zero Current
  values, while unknown completed-sale costs and profit remain explicit.
- Added web coverage for Pacific/UTC date boundaries, a day with no activity,
  missing costs, negative profit, total/current separation, and filter independence.
  The five focused chart tests and all 357 Python tests passed.
- Restarted the existing loopback-only web process with its original command,
  working directory, and environment. The live Sales page returned HTTP 200 with
  all eight summary labels and the expected current Pacific date.
- `./scripts/check.sh` passed: Python lint/formatting, all 357 Python tests,
  package compilation, dbt debug/parse/seed/build with all 126 build nodes passing,
  SQL lint, and the public-file policy. `git diff --check` passed; only the scoped
  application/test changes and required project notes are present in Git status.

### Keep exactly two summary rows

- The user reported four rows and clarified that Total and Current must each stay
  on one row. Strengthened the scoped four-column CSS rule so the shared mobile
  stacking rule cannot override it. Narrow viewports scroll within each row.
- Versioned the shared stylesheet URL so a previously cached three-column layout
  is refreshed with the updated styles. No calculations changed.
- All 46 focused Sales and static-asset tests passed. The full script was not
  repeated for this CSS/template-only correction after the preceding full pass.
- Chromium verified the live page at 1440, 900, 600, and 390 pixels: exactly two
  summary rows with all four cards sharing the same vertical position in each row.
  The browser also confirmed the versioned stylesheet URL. Browser verification
  used cached local shared libraries after the default launch lacked `libnspr4`.

### Active listed value and Today labels

- The user clarified that the lower Listed card should total everything currently
  selling. Added an unfiltered repository sum of active asking prices, exposed
  through the Sales service, and passed it to the summary separately from daily
  chart totals. Sold rows are excluded; an empty active inventory returns zero.
- The user's follow-up requested Listed Today, Sold Today, and corresponding
  labels. Asked about the conflict between Listed Today and the requested active
  inventory calculation. With no response during implementation, preserved both
  explicit requests: used the Today labels and retained the active inventory
  value. The adjacent note explains the distinction. Sold Today, Cost Today, and
  Profit Today remain based on today's Pacific completed sales.
- Extended existing tests for older active inventory, excluded sold listings,
  status/date/price filter independence, empty inventory, and selling/reopening
  transitions. The 56 focused Sales tests passed before the label follow-up; all
  four affected chart tests passed again with the final labels.
- `./scripts/check.sh` passed again: 357 Python tests, Python lint/formatting and
  compilation, dbt debug/parse/seed/build with 126 passing build nodes, SQL lint,
  and the public-file policy. `git diff --check` passed.
- Restarted the loopback web process with its existing command and environment.
  The live page and a sold-only price-filtered view both show 30,568,600 kamas
  for active inventory, matching an independent sum through the Sales service.

## Data navigation and performance dashboard

- Replaced the top-level Insights link with a Data dropdown containing Dashboard
  and Insights in alphabetical order. Existing Insights content and URL remain
  available. The new menu reuses click/keyboard handling, exclusive opening,
  outside-focus closing, and Escape behavior; the selected child stays identified.
- Added `/dashboard` as a read-only operational Sales projection. Used known
  realized profit as the proposed North Star, with its definition and cost
  coverage beside the main figure. The optional preference question received no
  different selection during implementation.
- Added 7-, 30-, and 90-day controls, defaulting to 30, anchored on today's Pacific
  date with a preceding equal-length comparison window. The page explicitly notes
  that today is partial and shows the last recorded sale time.
- Added daily realized-profit and revenue line charts, sales-volume bars,
  revenue/count/margin/time-to-sell KPIs, and coverage comparisons. Pointer,
  keyboard focus, and touch/click update a chart readout; a sortable daily table
  provides underlying values. All assets are local.
- Added an all-date active-inventory snapshot and selected-period top-five items
  by known profit. Snapshot totals remain distinct from period activity.
- Unknown sale cost stays excluded from both known profit and the margin revenue
  denominator. No-sale days are zero; sales whose profit is entirely unknown
  produce a line gap. Future sale timestamps are excluded, and stale history does
  not move the reporting window away from today.
- Service tests cover Pacific boundaries, preceding periods, losses, missing
  costs, cost coverage, margin, daily gaps/zeros, future timestamps, old active
  inventory, item ranking, empty data, and stale history. Web tests cover the
  Data navigation, reporting windows, empty views, and parameter validation.
- `./scripts/check.sh` passed: 363 Python tests, lint/formatting, compilation,
  dbt debug/parse/seed/build with all 126 build nodes passing, SQL lint, and
  public-file policy. `git diff --check` passed.
- Restarted the existing loopback web process with its command and environment.
  Chromium verified Data menu navigation, exclusive menu opening, the 7-day
  control, chart hover/focus readouts, and zero JavaScript errors on the live page.
  Browser checks passed at 1440, 900, and 390 pixels. The mobile pass identified
  and corrected a header-tab overflow; the inventory value now occupies a full
  mobile row. These final CSS adjustments were verified in the browser after the
  full suite. Screenshots stayed in `/tmp`, outside Git.

## Return web-server control to the terminal

- The user's manual `uv run dofus-web` failed because the agent-started background
  instance still owned port 8000. Confirmed that exact process and a successful
  Dashboard response, then gracefully stopped it so the user can start the app.
- Verified that `127.0.0.1:8000` can bind again. No application or data changes;
  full tests were not repeated for this process-only correction.

## Move BigQuery Sync under Data

- Moved BigQuery Sync from the top-level header into the Data dropdown, ordered
  BigQuery Sync, Dashboard, Insights. Data and the BigQuery Sync child are marked
  active on the existing sync page.
- The four focused navigation/page tests passed, along with Python lint,
  formatting, and `git diff --check`. A rendered-page inspection confirmed the
  dropdown order, active states, and absence of a top-level sync link.
- The full check script was not repeated for this navigation-template-only change.
  No sync job was started and no web-process restart was needed.
