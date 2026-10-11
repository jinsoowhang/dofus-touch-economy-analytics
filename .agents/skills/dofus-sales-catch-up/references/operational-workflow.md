# Local Sales workflow

Discover project paths through `Settings.from_env()`; the usual ignored database is
`data/app/dofus_touch.sqlite3`. Use the configured market. Read the current versions
of the named classes before preparing a private driver script.

## Match without writes

- Build `CaptureExtraction(screen_kind=ScreenKind.SOLD_NOTIFICATION,
  occurrences=tuple(...))` with `CaptureOccurrence(raw_item_name=...,
  displayed_price_kamas=..., image_number=..., row_number=...)` from
  `dofus_touch_economy.capture_schemas`. Track quantity separately: this planner's
  notification schema carries no quantity. Its existing equipment workflow is
  quantity one; other quantities require checking the listing grain, not expansion
  by guesswork.
- Call `SaleCaptureService(session, market_context,
  approved_professions=("Tailor", "Shoemaker", "Jeweller")).plan(
  CaptureAction.SOLD, extraction, observed_at=...)`. These are the established
  approved professions; do not silently broaden them.
- Require `plan.can_commit`. Inspect each row's disposition. Out-of-scope resources
  remain reported and unchanged; unresolved names, ambiguous catalog identities,
  or insufficient active listings block the batch. Pair actionable rows with
  `plan.changes` in order and validate their names/amounts. Retrieve each selected
  `SaleListing` by UUID for its ID and start timestamp.
- Matching reserves oldest exact-price active listings first, then the oldest
  remaining exact-item listing for a screenshot-authoritative price correction.
  Do not independently invent a different matching rule. Do not fabricate listings.

## Commit through services

Use `create_integrity_checked_backup` from `capture_evidence` for an online SQLite
backup, and rehearse against an isolated copy via `create_engine_for_url` and
`create_session_factory` from `database`. Audit the actual database path in each
run. Snapshot all operational tables for before/after comparison.

At live application, acquire `BEGIN IMMEDIATE`, compare the live state with the
backup, recheck evidence hashes, and regenerate/compare the capture plan and
allocation. If state changed, replan; do not overwrite it from the backup.
For each assigned date, call:

```python
SalesService(session, market_context).mark_listings_sold_at(
    listing_uuids,
    sold_at=assigned_aware_timestamp,
    source="manual_estimated_date",  # "manual" for a single-day interval
    capture_uuid=None,
    asking_prices={uuid: actual_screenshot_price for uuid in listing_uuids},
)
```

Group rows by timestamp/source and commit the entire batch once, after verification.
The service appends observations only for corrected prices, preserves original
listing starts, and calculates historical recipe cost at each assigned timestamp.
Existing observations stay immutable. Capture UUID is null for this local manual
workflow; do not manufacture Slack capture records.

Verify before commit and on saved SQLite: integrity and foreign-key checks; exactly
the selected listings changed; no listing created/deleted; original starts and
unrelated fields preserved; assigned timestamp, actual price, and source match the
plan; only necessary corrected-price observations appended; prior observations and
unrelated tables unchanged; sale count and revenue conserved. Record unknown-cost
coverage explicitly. Verify on the rehearsal copy first. If a commit completes but
report finalization fails, recover the audit from saved state instead of retrying
the sales transaction.

Useful existing tests:
`tests/python/test_sales.py`, `tests/python/test_sale_capture_service.py`.
Existing ignored manual audits/scripts may provide local examples, but are not
portable dependencies and should never be blindly replayed.
