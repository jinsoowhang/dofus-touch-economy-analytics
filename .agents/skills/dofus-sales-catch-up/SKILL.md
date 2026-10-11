---
name: dofus-sales-catch-up
description: Reconcile Dofus Touch sold-notification screenshots with local Sales listings and allocate missed reporting days using observed weekday sales trends. Use for sales catch-up or gaps between screenshot reports.
---

# Dofus sales catch-up

Work from the Dofus Touch economy repository. Read its `AGENTS.md`, `MEMORY.md`,
latest session notes, and [the operational workflow](references/operational-workflow.md).
This skill handles user-supplied screenshots and local SQLite Sales updates.

## Evidence and reporting interval

Find the user's Downloads directory, including its Windows mount when running in
WSL, and inspect each relevant image visually. Preserve complete occurrences in
screen order, including repeated identical sales. Remove only visually established
scroll overlap, never duplicates inferred from equal names/prices. Retain image and
row identifiers, visible quantity, exact name, whole-kama lot total, and SHA-256.
An unreadable sale requires review; unidentified expiration notices do not identify
a listing and cannot justify changing it. Do not infer a clipped sale.

Use committed private audits and session records to find the last actual reporting
checkpoint. `MAX(date_sold)` can contain estimated dates or unrelated manual edits;
it does not establish notification coverage. Check evidence hashes against prior
manual audits and capture-file records before planning a replay.

The established user-approved convention treats a catch-up batch as sales since
the previous report: allocate from the following Pacific calendar day through the
new screenshot's date, inclusive. Prefer an explicit supplied/filename date;
otherwise use the established screenshot save-time convention, documenting it as
a proxy. If the user says these are all sales since the last report, proceed under
that convention without requesting approval again. If there is evidence of an
intervening login, missing images, or an unclear date, prepare the transcript and
matches first, then clarify the material interval before writing affected sales.
Separate dated batches have separate intervals; do not distribute all screenshots
across one interval when they belong to different reporting checkpoints.

## Weekday allocation

Fit weights to mean completed-sale **counts per observed day** for each weekday,
correcting for unequal weekday exposure. Include zero-sale days only when a complete
check is established. Never treat unreported days as zero or train on
`manual_estimated_date` sales, other imputed dates, or partial observation days.
Use complete reporting days for the same market and approved profession scope.
The established baseline is August 22–September 12, 2026; reconstruct it from
non-estimated SQLite sales and verify against the previous audit. Extend or replace
it only with independently documented complete daily observations. Keep the
baseline dates, counts, exposure, and weights in the new private audit. Report that
small samples and inventory changes limit the estimate. Missing weekday exposure
or an all-zero eligible weight requires clarification, not invented trends.

Run the deterministic helper from the repository:

```bash
uv run python .agents/skills/dofus-sales-catch-up/scripts/allocate_sales.py \
  --input data/reports/catch-up-input.json \
  --output data/reports/catch-up-allocation.json
```

Input fields: `previous_reported_date` (ISO date), `observed_at` (aware timestamp),
`timezone` (normally `America/Los_Angeles`), `training_daily_counts` (ISO-date to
nonnegative whole sale-count mapping containing only verified complete days), and
`sales` (ordered records containing distinct `listing_uuid`, positive whole-kama
`asking_price`, and aware `selling_started_at`; extra evidence fields are retained).
SQLite naive timestamps represent UTC: attach UTC before constructing this input.

The helper allocates whole sales with exact rational arithmetic and largest
remainders, breaking ties by earlier date. It maps notification order to chronological
date slots, preserves each sale's price and total revenue, and rejects timestamps
before listing creation or after the evidence/current time. A temporal mismatch
requires reviewing matches or interval assumptions; do not silently move dates.
It writes a plan only and never connects to SQLite. Multi-day batches use
`manual_estimated_date`; single-day batches use `manual`. Daily revenue follows
the assigned actual transactions rather than invented fractional sales or prices.

## Apply and verify

Use the existing capture planner for exact identities, profession scope, active
listing counts, and deterministic listing matches. Follow the operational reference
to back up, rehearse on a copy, revalidate evidence/live state, and apply one atomic
batch through `SalesService`. A direct request to catch up local sales authorizes
that scoped update; do not add an approval round for a fully validated batch.
Preserve unrelated manual edits and original listing starts. Keep unknown historical
recipe costs null. Do not create missing listings or change unidentified expirations.

Retain the evidence dates, interval assumptions, training inputs, allocations,
original/assigned timestamps, prices, listing IDs, backup, and verification under
ignored `data/reports/`. Persist a planned audit before writing, and committed status
after successful saved-state verification. A planned or uncertain audit requires
checking SQLite before retrying. Do not replay an already committed batch.

Run focused Sales/capture tests, helper checks, lint/formatting, public-file policy,
and `git diff --check`. Update project memory/session notes with durable outcomes
and the skill location; keep private images/data/audits out of tracked files.
Report sale count, actual revenue, daily allocation, price corrections, and any
blocked rows. Explain that dates and resulting daily profit/timing metrics are
estimates. Current charts show assigned dates without estimate badges. Publishing
BigQuery snapshots, sending Slack messages, or changing the Slack pilot gates is
a separate action requiring its own user instruction.
