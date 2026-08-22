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
                 deferred immutable operational extract
                                |
                                v
                     ignored DuckDB raw schemas
                                |
                                v
                  dbt staging -> intermediate -> marts
```

`item_sales.csv` does not enter either implemented import path because its abbreviated dates and source-row grain are not deterministic.

## Operational boundary

SQLite owns transactional application state:

- import batches and accepted or rejected source-row provenance;
- imported or manually created canonical catalog identities, their creation source,
  and explicit source-name resolution decisions;
- normalized recipes and ordered ingredients;
- append-only manual lot-price observations and audit-preserving invalidation.

FastAPI reads and writes SQLite through repositories and services. Routers translate HTML or JSON only, and DuckDB receives no request-time writes. Alembic exclusively manages the operational schema. The default ignored database is `data/app/dofus_touch.sqlite3`.

The local browser interface uses server-rendered Jinja templates and a reviewed, vendored HTMX release. The JSON API under `/api/v1` calls the same services. Trusted hosts, same-origin browser mutations, and a loopback-only launch command define the current single-user security boundary.

The shared page layout owns a top-level tab navigation that can accept later pages.
The item-search tab renders alphabetical catalog summaries and uses one bulk latest-price
query for the active market context. Filtering replaces only the table fragment. Item
rows link to detail; price changes remain append-only observations rather than direct
edits.

Missing items may be created through the HTML or JSON interface. Similar-name results
are advisory and never establish identity. A later source import may enrich a sole
uncategorized manual item when its normalized name is unambiguous; stable UUIDs and
existing observations are preserved.

## Analytical boundary

DuckDB and dbt remain responsible for analytical state and governed transformations. A future milestone will extract immutable SQLite observations, identifiers, timestamps, market context, and provenance into DuckDB before building staging, intermediate, and mart models. The operational application must not be coupled to analytical model availability.

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
- SQLite-to-DuckDB extraction and dbt domain models;
- public hosting, authentication, authorization, and multi-user behavior;
- scraping, game-client automation, alerts, and dashboards.
