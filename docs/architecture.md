# Architecture

Objective: build a trustworthy analytical layer over player-observed Dofus Touch economy data while keeping source files private and local and keeping transformations reproducible.

## Boundaries

- `data/raw/` holds immutable local CSV exports and remains excluded from Git.
- Future Python code in `src/` will validate source contracts and load immutable raw DuckDB tables. That layer owns parsing, source row metadata, load metadata, and rejected-row reporting.
- dbt staging preserves source grain, standardizes names and types, and retains reconciliation values and parse status.
- dbt intermediate models normalize reusable concepts, including one row per recipe ingredient and deterministic exact-match item names.
- dbt marts document dimensions, facts, measures, grain, and intended consumers.
- Any semantic layer or BI tooling is deferred and must consume marts rather than bypass them.

## Data flow

```text
data/raw CSV
    -> Python validation with rejected rows and report
    -> DuckDB raw schema
    -> dbt staging / intermediate / marts
```

## Portability

Keep transformation SQL portable where practical. Isolate DuckDB-specific behavior in ingestion code and focused dbt macros instead of spreading engine-specific assumptions through every model.

## Current boundary

The repository does not implement ingestion or domain models yet. Those remain blocked until exact dates, row grains, and duplicate cost semantics are confirmed.
