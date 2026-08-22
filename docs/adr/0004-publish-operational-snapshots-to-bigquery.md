# ADR 0004: Publish operational snapshots to BigQuery

- Status: Accepted
- Date: 2026-08-22

## Context

The hosted BigQuery and dbt Developer pilot is connected, but the warehouse has no
deterministic source tables. Manually uploading the private CSVs would bypass the
application's validation, stable identities, timestamp rules, rejection records,
and audit-preserving price and Sales behavior. In particular, `item_sales.csv` still
has unresolved dates and row grain.

SQLite now contains the normalized operational state needed for analytics: catalog
items, source provenance, recipes, ingredients, price observations, and application
Sales listings with stable identifiers and deterministic timestamps.

## Decision

Publish content-addressed SQLite snapshots to the `dofus_dev` and `dofus_prod`
BigQuery base datasets through a repository-owned Python loader.

- Extract all contracted tables inside one read-only SQLite transaction.
- Reject any SQLite schema drift before uploading.
- Preserve normalized operational values and add a snapshot ID plus extraction time
  to every raw row.
- Partition raw tables by extraction date and cluster them by snapshot ID.
- Publish a manifest row only after all snapshot tables succeed.
- Make reruns idempotent by content hash and make partial retries replace only the
  incomplete hash.
- Authenticate the local loader with user ADC. Keep dbt Cloud's service-account JSON
  credential only in dbt Cloud.
- Point dbt sources at the target's base dataset and transform only the latest
  manifested snapshot.
- Continue excluding `item_sales.csv`; normalized application Sales rows are the
  sole hosted Sales source.

## Consequences

- Private analytical data is available to BigQuery and dbt without being committed
  or written to a public intermediate file.
- Interrupted loads can leave unmanifested raw rows, but dbt cannot select them and
  the next retry removes them before reloading.
- Every content change creates a new immutable warehouse snapshot. Historical raw
  snapshots consume storage until a separately approved retention policy exists.
- The public dbt project can reproduce schemas and transformations but cannot
  reproduce the user's private observations, which is intentional.
- The loader contract must be updated alongside intentional operational migrations.
- Local DuckDB remains useful for dbt parsing and CI, but the operational dbt models
  require the BigQuery raw snapshot until a separate local bridge is implemented.
