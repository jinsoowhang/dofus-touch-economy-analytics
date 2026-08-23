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
  and explicit source-name resolution decisions;
- normalized recipes and ordered ingredients;
- append-only manual lot-price observations and audit-preserving invalidation.

FastAPI reads and writes SQLite through repositories and services. Routers translate HTML or JSON only, and DuckDB receives no request-time writes. Alembic exclusively manages the operational schema. The default ignored database is `data/app/dofus_touch.sqlite3`.

The local browser interface uses server-rendered Jinja templates and a reviewed, vendored HTMX release. The JSON API under `/api/v1` calls the same services. Trusted hosts, same-origin browser mutations, and a loopback-only launch command define the current single-user security boundary.

The shared page layout exposes Item and Sales as top-level navigation. Item opens an
accessible hover, click, and keyboard-focus submenu for Item Search and Recipes. Item
Search renders alphabetical catalog summaries and uses one bulk latest-price query
for the active market context. Filtering replaces only the table fragment. Item rows
link to detail; price changes remain append-only observations rather than direct
edits. Recipes selects the latest recipe per crafted item, resolves current prices in
bulk, derives standard profession-slot requirements and crafting economics, and
provides URL-backed filters and sortable columns without mutating recipe data. Its
Current Price cells append quantity-one observations on Enter or blur, preserve the
active recipe view, and recalculate row economics without creating Sales listings.

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

DuckDB and dbt Core remain the reproducible local profile and CI parse path during
the pilot. The operational dbt models require hosted raw tables until an equivalent
local SQLite-to-DuckDB bridge is implemented.

Transformation SQL should remain portable where practical. DuckDB-specific behavior belongs in focused ingestion code or macros.

## Source ownership

- `data/raw/` contains immutable, ignored local CSV exports.
- `data/reports/` contains ignored validation and conflict reports.
- `data/app/` contains ignored mutable SQLite operational state.
- `data/warehouse/` contains ignored DuckDB analytical state.
- Tracked tests use invented synthetic fixtures only.

Imported cost values and spreadsheet-derived totals, profit, and ROI remain reconciliation provenance. Current prices and governed crafting metrics are recomputed from valid manual observations; missing or unresolved inputs never become zero.

## Deferred boundaries

- `item_sales.csv` ingestion until its dates and grain are deterministic;
- SQLite-to-DuckDB extraction for local execution parity;
- public hosting, authentication, authorization, and multi-user behavior;
- scraping, game-client automation, alerts, and dashboards.

## Hosted analytical pilot

A dbt Developer and BigQuery pilot executes the dbt project against private,
contract-approved operational snapshots. Local dbt Core and DuckDB remain the
canonical reproducible parse path until hosted model parity is demonstrated.

See
[the setup guide](dbt-cloud-bigquery-setup.md) and
[the ingestion guide](operational-bigquery-ingestion.md), plus
[ADR 0003](adr/0003-pilot-dbt-platform-and-bigquery.md) and
[ADR 0004](adr/0004-publish-operational-snapshots-to-bigquery.md).
