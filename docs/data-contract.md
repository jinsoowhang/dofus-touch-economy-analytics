# Data contracts

## Shared source rules

- Source files are UTF-8 CSV with commas and one header row; a UTF-8 BOM is accepted.
- Raw source values and source-row numbers remain available for reconciliation.
- Raw files are immutable inputs and are never rewritten by the importer.
- File-level encoding or header failures abort before database writes.
- Row-level failures are retained as rejected source records while valid rows load transactionally.
- Names are normalized by trimming and collapsing whitespace and applying Unicode case folding. Fuzzy identity repair is excluded.

## Application import scope

### `item_cost.csv`

The exact source-order header is:

```text
raw_material,category,price
```

Material and category are required. Canonical identity uses normalized item name plus normalized category, so duplicate names in different categories remain distinct. The raw `price` value is preserved for reconciliation but does not create a current-price observation because the export lacks a deterministic observation timestamp.

### `item_recipes.csv`

The exact source-order contract contains `recipe_item`, `profession`, eight repeated `raw_material_n`, `quantity_n`, `cost_n` groups, then `total_cost`, `profit`, and `ROI`.

Recipe item and profession are required. Within each ingredient position, material and quantity are either both blank or both present; quantity must be a positive base-10 integer after comma removal. Populated groups become ordered recipe ingredients. Source costs and derived totals remain raw reconciliation values.

Exact normalized names resolve automatically only when one candidate exists. Ambiguous ingredient names remain unresolved and make recipe metrics incomplete. No partial or fuzzy match establishes identity.

### `item_sales.csv`

Sales ingestion remains deferred. The source has abbreviated dates, no stable transaction identifier, no quantity, and an unresolved listing-versus-sale row grain. Missing years must never be inferred.

## Operational catalog identities

The local application may create an item manually when search has no result. Manual
commands require an exact display name and accept an optional category. Identity uses
the same normalized name and normalized category key as imports, and each item records
whether it was first created manually or by import.

Manual display names and entered category overrides are whitespace-normalized and
title-cased. When category is omitted, the application may infer one only from a
reviewed equipment type appearing as the complete final word. Recognized suffixes are
amulet, axe, belt, boots, bow, cape, cloak, dagger or daggers, hammer, hat, ring,
shield, shovel, staff, sword, and wand. An explicit category overrides inference.

An exact existing identity is not duplicated. If category is omitted, any existing
exact-name candidate blocks creation when no category can be inferred so the user can
select the existing item. Similar names are suggestions only and never merge
automatically. A cost import may add a category to a sole uncategorized manual item
with the same normalized name; the item UUID, creation provenance, and observations
remain unchanged.

## Operational price observations

Manual observations persisted by the application contain:

- stable observation UUID and monotonic internal ordering identifier;
- canonical item UUID;
- positive integer lot quantity;
- positive whole-kama total price;
- timezone-bearing observation timestamp;
- database recording timestamp;
- configured market context;
- optional note and fixed `manual` source;
- optional paired invalidation timestamp and required reason.

Unit price is derived with decimal arithmetic as `total_price / lot_quantity`. The current price for an item is the latest valid observation in the active market context ordered by:

1. observation timestamp descending;
2. recording timestamp descending;
3. internal observation identifier descending.

Invalidated observations remain in history but never participate in current-price or crafting calculations. An observation is invalidated once with a reason; direct edits and hard deletion are not application operations.

## Governed crafting calculations

The website derives the standard minimum profession level from the number of
populated recipe ingredient slots: one or two ingredients require level 1, then
three through eight ingredients require levels 10, 20, 40, 60, 80, and 100. This is
a governed display rule, not a source field. The live payload's `resultLevel` is the
recipe result level and must not be relabeled as a profession requirement. A recipe
without ingredients has an unknown required profession level.

```text
ingredient cost = required quantity * current ingredient unit price
recipe cost = sum of ingredient costs
profit = current crafted-item unit price - recipe cost
ROI = profit / recipe cost
```

Recipe cost is incomplete when an ingredient is unresolved or lacks a current valid price. Profit requires a complete recipe and a current crafted-item price. ROI is absent when recipe cost is zero. Missing values are never treated as zero.

## Hosted analytical snapshot

The BigQuery loader reads the normalized SQLite tables, not the source CSV files. Its
contract preserves:

- stable UUIDs and internal relationship identifiers;
- source filename, row number, raw payload, validation messages, and import checksum;
- recorded, observed, listing-started, sold, and invalidation timestamps;
- market context, invalidation state, and Sales status;
- a stable content-derived snapshot ID and UTC extraction timestamp.

All contracted tables are read inside one SQLite transaction. Any missing or
unexpected column, required null, or invalid timestamp fails extraction. BigQuery
raw rows become eligible for dbt only after the loader writes the snapshot manifest.
This immutable analytical ingestion remains separate from request-time application
writes.

The loader does not resolve the deferred `item_sales.csv` contract. Hosted Sales data
comes from the normalized `sale_listings` application table only.
