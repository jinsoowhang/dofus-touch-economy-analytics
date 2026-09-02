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

The live Dofus Touch catalog may enrich an exact matched item with `realWeight`, a
nonnegative integer carrying weight measured in pods. Zero is valid. Items without a
valid or unambiguous live match keep a null weight; missing weight is never converted
to zero. This enrichment preserves item identity, provenance, recipes, prices, and
Sales history.

Every catalog sync also compares every local normalized item name against all names
in Ankama's current English Dofus Touch `Items` payload, including non-exchangeable
items. A reviewed legacy-name alias counts as the corresponding current Touch name.
The result, check timestamp, and exclusion reason are persisted on the item. Items
absent from that authoritative catalog are hidden from website catalog, recipe,
price, and Sales surfaces, and recipes containing an excluded ingredient are hidden
as well. Rows are never deleted: imports, observations, listings, and analytical
provenance remain available for audit. Items not yet checked remain visible until a
successful catalog sync records a result.

The same sync may refine only the catch-all `Resource` display category. It prefers
the exact current Dofus Touch item type, then an exact DofusDB legacy-item match when
every returned candidate has the same non-generic type. A missing or conflicting
match remains `Resource`; specific existing categories are never overwritten. The
normalized import category remains `identity_category`, so later source imports
continue to resolve the same stable item rather than creating a new identity.

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

Recipe Calculator Sales submission is an explicit operational mutation. Each unique
checked craftable item requires a positive whole-kama Sale Price and creates exactly
one active `sale_listings` row plus its linked quantity-one price observation. Craft
Quantity remains a recipe-planning value and does not determine listing count. The
batch validates every row before writing and commits atomically; any invalid price,
identifier, or stale recipe prevents all listings in that submission.

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

When an active listing is marked sold, the application snapshots the complete recipe
ingredient cost known at that sale timestamp. Completed-sale profit is then fixed as
the recorded asking price minus that nullable snapshot; later ingredient observations
do not rewrite realized profit. Legacy completed listings without a stored snapshot
may be reconstructed from the known recipe definition and ingredient price
observations recorded no later than their sale timestamp. If that history is
incomplete, sale cost and profit remain null.

For a confirmed Slack `sold` capture, exact-price active listings are reserved first.
If an exact item has remaining screenshot occurrences and remaining active listings,
the oldest remaining listing is corrected to the screenshot price before it is marked
sold. Each correction appends a linked quantity-one price observation at the Slack
message timestamp with `slack_sold_capture` provenance. Price correction, sale state,
cost snapshot, lineage, and capture audit writes share one transaction. The capture
never fabricates a missing listing, and insufficient active item counts block the
entire batch.

## Hosted analytical snapshot

The BigQuery loader reads the normalized SQLite tables, not the source CSV files. Its
contract preserves:

- stable UUIDs and internal relationship identifiers;
- source filename, row number, raw payload, validation messages, and import checksum;
- recorded, observed, listing-started, sold, and invalidation timestamps;
- market context, invalidation state, and Sales status;
- nullable fixed recipe cost at sale for completed listings;
- nullable generic listing/sale source and capture UUID lineage;
- nullable live-catalog item weight in pods;
- nullable Dofus Touch membership status, check timestamp, and exclusion reason;
- a stable content-derived snapshot ID and UTC extraction timestamp.

All contracted tables are read inside one SQLite transaction. Any missing or
unexpected column, required null, or invalid timestamp fails extraction. BigQuery
raw rows become eligible for dbt only after the loader writes the snapshot manifest.
This immutable analytical ingestion remains separate from request-time application
writes.

The loader does not resolve the deferred `item_sales.csv` contract. Hosted Sales data
comes from the normalized `sale_listings` application table only.

Screenshot capture tables are not part of the hosted contract. Slack workspace,
channel, user, message, and file identifiers; captions; evidence paths and hashes;
model response IDs; extraction payloads; review details; and receipt state remain
local. A confirmed listing may carry only the generic nullable
`listing_source`/`listing_capture_uuid` and `sale_source`/`sale_capture_uuid` fields.
