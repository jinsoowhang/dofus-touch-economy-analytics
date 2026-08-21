# Memory

**Last updated:** 2026-08-20

## Dofus Touch Economy Analytics

- Public identity: analytics engineering for player-observed Dofus Touch item prices, crafting economics, sales behavior.
- Local stack: Python 3.12, uv, dbt Core, dbt-duckdb, DuckDB.
- Approved application milestone: a loopback-only FastAPI/Jinja/vendored-HTMX website with SQLite owning operational state while DuckDB and dbt remain the analytical layer.
- Application prices are append-only lot observations with audit-preserving invalidation; imported cost values are provenance, not current market observations.
- dbt layers: staging, intermediate, marts.
- Raw CSVs, DuckDB, secrets, task-observer files, and worktrees stay local and ignored.
- Canonical local sources: `item_sales.csv`, `item_recipes.csv`, and `item_cost.csv` under `data/raw`.
- Only synthetic samples may be committed until redistribution rights are established.
- Current CSV abbreviated dates mean ingestion and date-dependent models require deterministic ISO dates from a re-export or an explicitly approved parsing rule; never infer missing years.
- Source-derived costs, profits, differences, and ROI are preserved for reconciliation but recomputed as governed measures.
- `item_cost.csv` and `item_recipes.csv` are included in the application importer; `item_sales.csv` remains deferred until its dates and grain are deterministic.
- Implementation checkpoint: application packaging and local-state protection are complete; deterministic settings and the SQLite engine/session boundary pass tests and spec review, with two portability findings awaiting investigation.
- Next milestone: close the SQLite in-memory pooling and URL-path quality findings, then implement the operational schema and Alembic migration.
