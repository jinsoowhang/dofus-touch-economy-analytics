# ADR 0001: Use dbt Core and DuckDB locally

- Status: Accepted
- Date: 2026-08-20

## Context

The project starts from three local CSV exports and needs analytics engineering conventions, reproducible transformations, tests, and documentation without paid cloud infrastructure.

## Decision

Use dbt Core with `dbt-duckdb`, keep the local DuckDB database ignored from Git, and manage the Python environment with `uv`.

## Consequences

- The stack stays local and requires no external accounts.
- dbt provides lineage, tests, documentation, and clear staging/intermediate/marts layers.
- DuckDB-specific behavior should stay isolated so transformation SQL remains portable where practical.
- Hosted warehouses and semantic or BI tools such as Lightdash stay deferred.
- Raw data remains local, and CI stays independent of private source files.
