# Architecture

The project separates mutable local application state from reproducible downstream analytics while keeping all observed source data private.

## System flow

```text
ignored item_cost.csv + item_recipes.csv
                    |
                    v
        strict contracts + import service
          |                         |
          v                         v
 ignored JSON report       ignored SQLite database
                                ^           |
                                |           v
      manual item command -> FastAPI services -> Jinja + HTMX / JSON API
                                ^
                                |
 private Slack images -> local Socket Mode worker -> Codex CLI extraction
                                |
                                v
                    immutable snapshot extract
                                |
                                v
                   private BigQuery raw schemas
                                |
                                v
                  dbt staging -> intermediate -> marts
```

`item_sales.csv` does not enter either implemented import path because its abbreviated dates and source-row grain are not deterministic.

Hosted analytical flow:

```text
normalized SQLite state
    -> content-addressed raw BigQuery snapshots
    -> latest manifested snapshot
    -> dbt Developer staging / intermediate / marts
```

The hosted flow does not authorize manual upload of private raw exports. The loader
publishes the application's contract-approved normalized state, including provenance,
invalidations, stable IDs, timestamps, and extraction metadata. It never reads the
ambiguous sales CSV.

## Operational boundary

SQLite owns transactional application state:

- import batches and accepted or rejected source-row provenance;
- imported or manually created canonical catalog identities, their creation source,
  Dofus Touch carrying weight and exact-match resource subtype when available, and
  explicit source-name resolution decisions;
- normalized recipes and ordered ingredients;
- append-only manual lot-price observations and audit-preserving invalidation;
- private screenshot intake, evidence metadata, retry/review state, confirmations,
  and listing-action audit history.

FastAPI reads and writes SQLite through repositories and services. Routers translate HTML or JSON only, and DuckDB receives no request-time writes. Alembic exclusively manages the operational schema. The default ignored database is `data/app/dofus_touch.sqlite3`.

The optional Slack Bolt Socket Mode worker is a separate local process with its own
secret-bearing configuration. It persists allowlisted top-level message intake before
acknowledgement, downloads private image bytes into ignored evidence storage, and asks
a local, ChatGPT-authenticated `codex exec` subprocess for strict structured
extraction. Each invocation is ephemeral, ignores user configuration and execution
rules, disables shell, multi-agent, local-image-tool, and web-search access, runs in a
temporary directory with a read-only sandbox, and receives only an allowlisted process
environment. The model has no database context and cannot select the action.
Deterministic services plan and revalidate Sales changes. A `sold` capture reserves
exact-price matches first, then may correct the oldest remaining active listing for
the exact item to the screenshot price before marking it sold. Owner confirmation,
an integrity-checked backup, and one SQLite transaction precede each mutation.
Receipt delivery is a separate retryable side effect. Live marketplace extraction
remains disabled until its private layout gate is met.

The local browser interface uses server-rendered Jinja templates and a reviewed, vendored HTMX release. The JSON API under `/api/v1` calls the same services. Trusted hosts, same-origin browser mutations, and a loopback-only launch command define the current single-user security boundary.

The shared page layout exposes Home, Item, Sales, and Data as top-level navigation.
Data contains BigQuery Sync, Dashboard, and Insights. Menus open by click or keyboard and close
when another menu opens, focus leaves, or Escape is pressed.
Item opens an accessible submenu for Item Search,
Recipes, and Recipe Calculator; Sales uses the same pattern for Sales Activity, Best
Sellers, Out of Stock Items, Price Review, and Profit Opportunities. Item Search renders 100-row pages of alphabetical
catalog summaries and uses one bulk latest-price query for the active market context.
Filtering replaces only the table fragment. Item rows link to detail; price changes remain append-only
observations rather than direct edits. Recipes selects the latest recipe per crafted
item, resolves current prices in bulk, derives standard profession-slot requirements
and crafting economics through a scalar projection instead of hydrating every recipe
ORM relationship. It provides 100-row pages, URL-backed filters—including one
dual-handle profession-level range synchronized with numeric endpoints—and sortable
columns without mutating recipe data. Its Current Price cells append quantity-one
observations on Enter or blur, preserve the active recipe view, and recalculate row
economics without creating Sales listings. Item-detail ingredient prices expose
calendar-day age and become stale at seven days.

All data-bearing tables expose sortable data headers. Paginated Item Search, Recipes,
and Sales tables sort on the server while detail, calculator, out-of-stock, and daily
summary tables use one local typed sorter. Selection and action-only columns remain
controls rather than misleading sort targets.

Home (`/`) is the default landing page. Five aggregate SQLite reads provide live
sales/inventory context without loading recipe economics or the full Dashboard.
The daily checklist follows Sales Activity, Out of Stock Items, Profit Opportunities,
and the 7-day Dashboard, with Price Priorities added on Mondays and relisting on
Fridays. Checkmarks are manual browser-local state for the current Pacific date;
navigation does not imply task completion. Midnight and stale-page checks refresh
the routine, and cross-tab storage events synchronize completion. No UI telemetry
or operational write is introduced by the checklist.

Craftable-item price entry uses thousands of kamas with explicit labels and examples.
Ingredient Per Unit Price always uses full kamas, including craftable intermediates.
Mixed Item Search/detail and Price Priorities views choose units by recipe membership;
search and priority pages use one bulk lookup for their displayed items. Templates
format prefills and unchanged-value baselines in the field's unit. Explicitly marked
thousands forms convert back to whole kamas with exact Decimal arithmetic at the web
boundary; full-kama forms pass through unchanged. Calculator Sale Price Each and its
live revenue estimates retain the thousands scale. Read-only amounts, storage, API
commands, and unmarked suggestions remain canonical kamas. Sales price-filter
submissions convert once and navigation links retain canonical query amounts.

Sales Activity focuses on managing existing listings; the Add an Item to Sell form
and its picker queries/client handlers are removed. Recipe Calculator listing creation
and existing write endpoints remain available. Active and sold tables paginate
independently at 50 rows.
Full matching counts, asking-price totals, and cost/profit sorting are computed
before pagination; the daily chart always uses unfiltered history. Bulk selection
is explicitly limited to the current page. A request materializes sold history
once and shares it with daily totals. Current recipe costs load only the latest
recipe versions and requested ingredient prices; historical reconstruction keeps
its existing timestamp rules. Page payloads are bounded, while server calculations
and filtering still scale with full listing history.

Price Review (`/sales/price-review`) projects active listings whose latest relist,
or original listing date, is at least fourteen Pacific calendar days old. Each row
retains listing identity; missing-price rows remain eligible. Server sorting and
50-row pagination accompany full due counts and listed value. Price changes reuse
the Sales service and append a linked price observation, preserving the original
listing start while recording the relisted date. The updated listing leaves the
queue until fourteen more days pass. Item-level observations do not reset this clock.
Current recipe cost, estimated profit, suggestion profit, and observed item-price
context support manual decisions; unknown cost remains explicit. Sales Price is
read-only on this page; a separate blank Relist Price field accepts a new price.
The Action column can snooze a due listing for exactly seven days. Alembic `0011`
persists this deadline separately from listing and relist dates; snooze changes no
price observations. Repricing clears it, and all review reminders and Home's count
exclude unexpired snoozes. The raw snapshot contract carries the nullable snooze
timestamp. No game-client action is involved.

The Recipe Calculator is an operational projection over the latest recipe per
crafted item and the latest valid ingredient prices. Resolved shopping-list prices
can append quantity-one observations through an inline editor; a successful save
recalculates the selected recipes without creating Sales listings. User-selected craft
quantities and calculation selections remain separate browser-local cart state and
non-authoritative request state. Unchecked items stay in the cart but are omitted from
the submitted calculation. Each shopping-list row retains its craft attribution,
while a second quantity reports the canonical ingredient total across every selected
craft. Each row includes catalog category, official pod weight, quantity-adjusted
total weight, and current-price freshness. The calculator reports a
complete total weight only when every ingredient weight is known, and restores the
previous scroll offset after an inline price edit recalculates the page. Unresolved
identities and missing prices remain explicit.

An independent Sell checkbox and editable whole-kama Sale Price appear beside each
cart row. The explicit bulk action validates that every checked item still has a
current recipe, then atomically creates one active Sales listing and one append-only
price observation per checked row before redirecting to Currently Selling. Craft
Quantity remains calculation-only and never multiplies listings. Invalid input writes
none of the batch; the calculator still never mutates recipe definitions.

Out of Stock Items is a grouped Sales projection: an item qualifies when it has at
least one completed listing and zero active listings. It uses the most recent sold
listing plus bulk current-price and recipe-cost calculations, and exposes craftable
items through the shared browser-local Recipe Calculator cart without adding listings.

Dashboard is a read-only Sales projection with known realized profit as its North
Star. Its 7-, 30-, and 90-day controls end on today's Pacific calendar date and
compare against the preceding equal-length period; today is explicitly partial.
Category multi-select and item-name substring filters apply to both comparison
periods, every chart/KPI, top items, and the current inventory snapshot; categories
combine with OR and name matching with AND. Time links preserve these URL filters.
Daily profit plots known subtotals consistently with the headline and daily table.
Partial-cost days remain connected using dashed lines and hollow points with explicit
coverage/subtotal readouts. Wholly unknown profit has a gap and a marker below the
plot; no-sale days remain zero and losses remain negative. Revenue and volume
include all matching sales. Margin uses only revenue from sales with known costs, and
cost coverage accompanies profit. Current inventory is a separate all-date
snapshot. These views use the operational SQLite services without hosted queries.

Insights is a read-only operational synthesis over the existing Sales and recipe
services. It compares the seven calendar days ending on the latest recorded Pacific
sale date with the preceding seven days, then combines volume, revenue, selling
velocity, revenue concentration, historical cost coverage, current inventory
attention, crafting opportunities, and category performance. It does not write data
or depend on request-time DuckDB, BigQuery, or dbt availability.

BigQuery Sync is a process-local, single-run background controller around the same
fixed snapshot loader used by the CLI. The loopback web page cannot supply commands
or targets. It polls capped, timestamped progress output that contains schema IDs,
table names, and counts but no source rows or credentials. The controller inherits
the local process's Application Default Credentials, retains only the latest run in
memory, and publishes BigQuery raw snapshots without invoking dbt Cloud.

Missing items may be created through the HTML or JSON interface. Similar-name results
are advisory and never establish identity. A later source import may enrich a sole
uncategorized manual item when its normalized name is unambiguous; stable UUIDs and
existing observations are preserved.

## Analytical boundary

BigQuery and dbt own hosted analytical state and governed transformations. The
snapshot loader reads SQLite in one consistent transaction, validates an exact table
contract, derives a content hash, and appends partitioned raw rows to both base
datasets. A manifest is written last; dbt filters every source to the newest complete
manifested snapshot. The operational application is not coupled to analytical model
availability.

BigQuery tables reject incompatible or unexpected schema changes. A new nullable
contract column may be appended in place so existing immutable rows remain valid with
null values; required additions and type changes still stop publication for review.

DuckDB and dbt Core run the reproducible local and CI build against small synthetic
relations that implement the operational snapshot contract. The fixtures are enabled
only for DuckDB; real operational data remains private and reaches dbt only through
the manifested BigQuery loader.

Transformation SQL should remain portable where practical. DuckDB-specific behavior belongs in focused ingestion code or macros.

## Source ownership

- `data/raw/` contains immutable, ignored local CSV exports.
- `data/reports/` contains ignored validation and conflict reports.
- `data/app/` contains ignored mutable SQLite operational state.
- `data/app/slack_sales_evidence/` and `data/app/backups/` contain ignored private
  screenshot evidence and recovery databases.
- `data/warehouse/` contains ignored DuckDB analytical state.
- Tracked tests use invented synthetic fixtures only.

Imported cost values and spreadsheet-derived totals, profit, and ROI remain reconciliation provenance. Current prices and governed crafting metrics are recomputed from valid manual observations; missing or unresolved inputs never become zero.

## Deferred boundaries

- `item_sales.csv` ingestion until its dates and grain are deterministic;
- SQLite-to-DuckDB extraction for local execution against private operational data;
- public hosting, authentication, authorization, and multi-user behavior;
- scraping, game-client automation, Slack autonomy, alerts, and external BI dashboards.

## Hosted analytical pilot

A dbt Developer and BigQuery pilot executes the dbt project against private,
contract-approved operational snapshots. Local dbt Core and DuckDB remain the
credential-free contract, transformation, and data-test verification path.

See
[the setup guide](dbt-cloud-bigquery-setup.md) and
[the ingestion guide](operational-bigquery-ingestion.md), plus
[ADR 0003](adr/0003-pilot-dbt-platform-and-bigquery.md) and
[ADR 0004](adr/0004-publish-operational-snapshots-to-bigquery.md).
