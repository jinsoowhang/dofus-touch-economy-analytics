# Session Notes 2026-09-01

## Slack sold price correction

### Decision

- A confirmed `sold` screenshot is authoritative for the completed listing's Sales
  Price after exact catalog identity has been established.
- Exact-price active listings are reserved first. Remaining screenshot occurrences
  use the oldest remaining active listing for the exact item, ordered by listing start
  and internal ID.
- The worker still never fabricates missing listings. Insufficient active item counts,
  ambiguity, extraction warnings, or timestamp conflicts keep the entire multi-image
  batch in review with no Sales writes.

### Behavior

- The confirmation preview shows mismatched prices as an old-to-new correction before
  the listing is marked sold.
- Confirmation appends a linked quantity-one `slack_sold_capture` price observation,
  updates the listing price, snapshots recipe cost, marks the listing sold, writes
  capture lineage and action history, and commits the full batch atomically.
- One top-level Slack message with multiple images continues to form one ordered,
  atomic batch. No schema or Slack-permission change was required.
- Updated the README, architecture, data contract, Slack runbook, and implemented
  design to reflect the new confirmation-required rule. The correction path must be
  included in private evaluation before any autonomy review.

### Verification

- Focused capture service, Sales primitive, Slack worker, and vision verification
  passed (31 tests).
- A live two-image message was durably ingested and extracted by the pre-restart
  worker, confirming multi-image intake. It remained in review with no Sales writes
  because both images contained a clipped top row and the running process still used
  the prior exact-price rule.
- A read-only rehearsal of that ignored local batch with the new code proposed 38
  Sales changes, including seven price corrections, with one out-of-scope row. Only
  the two partial-row extraction warnings remained; no Sales data was changed by the
  rehearsal.
- `./scripts/check.sh` passed: Ruff lint and formatting, 349 Python tests, package
  compilation, dbt debug/parse, nine seed loads, all 126 dbt build nodes, SQLFluff,
  and public-file policy.

## Slack action-selection feedback

### Behavior

- A successful owner click on **Sold** or **Market** immediately replaces the action
  buttons with `⏳ <Action> selected — processing screenshots…`.
- The processing state is non-interactive and reuses the original action-selection
  message for the eventual confirmation preview or terminal review result, preventing
  stale controls or a stranded loading message.
- The Bolt handler still acknowledges the interaction before the database transition
  and Slack message update. Unauthorized or stale clicks produce no misleading status
  change.
- Slack Block Kit has no standard persistent animated spinner element, so the worker
  uses the reliable hourglass status instead of repeated rate-limited message edits.

### Verification

- Focused capture-repository and Slack worker verification passed (15 tests),
  including immediate feedback, same-message preview replacement, confirmation, and
  rejection behavior.
- `./scripts/check.sh` passed: Ruff lint and formatting, 349 Python tests, package
  compilation, dbt debug/parse, nine seed loads, all 126 dbt build nodes, SQLFluff,
  and public-file policy.

## Listed value in Sales Over Time

### Behavior

- Added a blue Listed series to Sales Over Time. It includes active and completed
  listings, groups each listing by its Pacific `selling_started_at` date, and sums
  the listing's recorded Sales Price.
- The chart's event-date domain is the union of listed and sold dates. Listed remains
  independent of the visible Sales table filters, matching the existing historical
  series behavior.
- Added Listed to the KPI strip and daily totals table, and changed the shared date
  label from Date Sold to Date because the chart now combines listed and sold dates.
- All Sales, All Cost, and All Profit retain their completed-sale semantics and group
  by Pacific date sold. Missing Cost at Sale remains excluded rather than treated as
  zero.

### Verification

- Focused Sales service and Web UI verification passed (101 tests), including active
  plus completed listed totals, Pacific date grouping, filter independence, the
  four chart series, and the daily table presentation.
- `./scripts/check.sh` passed: Ruff lint and formatting, 350 Python tests, package
  compilation, dbt debug/parse, nine seed loads, all 126 dbt build nodes, SQLFluff,
  and public-file policy.
- Restarted the loopback Web UI and confirmed the real ignored database renders the
  Listed KPI, line, and point labels with HTTP 200; no operational values were copied
  into tracked files.
