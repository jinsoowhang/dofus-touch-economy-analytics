# Memory

**Last updated:** 2026-08-20

## Dofus Touch Economy Analytics

- Public identity: analytics engineering for player-observed Dofus Touch item prices, crafting economics, sales behavior.
- Local stack: Python 3.12, uv, dbt Core, dbt-duckdb, DuckDB.
- dbt layers: staging, intermediate, marts.
- Raw CSVs, DuckDB, secrets, task-observer files, and worktrees stay local and ignored.
- Canonical local sources: `item_sales.csv`, `item_recipes.csv`, and `item_cost.csv` under `data/raw`.
- Only synthetic samples may be committed until redistribution rights are established.
- Current CSV abbreviated dates mean ingestion and date-dependent models require deterministic ISO dates from a re-export or an explicitly approved parsing rule; never infer missing years.
- Source-derived costs, profits, differences, and ROI are preserved for reconciliation but recomputed as governed measures.
- Next milestone: test-driven source-contract validation and immutable DuckDB loading.
