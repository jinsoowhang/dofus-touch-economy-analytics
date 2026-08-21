# Memory

**Last updated:** 2026-08-21

## Dofus Touch Economy Analytics

- Public identity: analytics engineering for player-observed Dofus Touch item prices, crafting economics, sales behavior.
- Local stack: Python 3.12, uv, FastAPI, Jinja, vendored HTMX, SQLAlchemy, Alembic, SQLite, dbt Core, dbt-duckdb, and DuckDB.
- Implemented application: a loopback-only FastAPI/Jinja/vendored-HTMX website with versioned JSON endpoints. SQLite owns operational state while DuckDB and dbt remain the downstream analytical layer.
- Application prices are append-only observations with audit-preserving invalidation; Item Search records total price with implicit quantity one, while imported cost values remain provenance rather than current market observations.
- dbt layers: staging, intermediate, marts.
- Raw CSVs, SQLite and DuckDB databases, import reports, secrets, task-observer files, and worktrees stay local and ignored.
- Canonical local sources: `item_sales.csv`, `item_recipes.csv`, and `item_cost.csv` under `data/raw`.
- Only synthetic samples may be committed until redistribution rights are established.
- Current CSV abbreviated dates mean ingestion and date-dependent models require deterministic ISO dates from a re-export or an explicitly approved parsing rule; never infer missing years.
- Source-derived costs, profits, differences, and ROI are preserved for reconciliation but recomputed as governed measures.
- `item_cost.csv` and `item_recipes.csv` are included in the application importer; `item_sales.csv` remains deferred until its dates and grain are deterministic.
- Item identity uses whitespace-collapsed Unicode case-folded exact names. Cost identities also include normalized category; ambiguous recipe ingredients remain unresolved rather than being guessed.
- A no-result search offers advisory close-name links and manual item creation. Similarity never establishes identity, exact duplicates are blocked, and each item records whether it was first created by import or manually.
- Manual item names and entered category overrides are whitespace-normalized and title-cased. When category is omitted, a reviewed final-word equipment suffix may infer it; explicit category input wins and arbitrary substrings never classify an item.
- The shared page header exposes Item Search and Sales as top-level tabs. A blank item query renders the full alphabetical catalog; typing filters it by normalized name.
- Catalog rows include category, latest valid total price, and observation time for the active market. Prices are selected in one bulk window query, and every row cell opens item detail for append-only price entry rather than direct mutation.
- Sales listings record item, lot quantity, `selling_started_at`, and nullable `date_sold`. Recording a price automatically creates a linked active listing; direct Sales entries support arbitrary lot quantities, and marking one sold moves it into history.
- For small application iterations, avoid broad README/design-document edits unless a public contract changes or the user asks; still maintain the required `MEMORY.md` and dated session note at session end.
- A later cost import may enrich a sole uncategorized manual item with its category while preserving the stable UUID, manual creation provenance, recipes, and price observations.
- The application importer validates both file contracts before writes, is idempotent by dataset checksum, preserves accepted and rejected raw-row provenance locally, and never promotes imported cost values into current price observations.
- Additive SQLite migrations for referenced tables should use supported direct `ALTER TABLE` operations rather than batch table rebuilds while foreign-key enforcement is active; populated upgrade tests must include dependent rows.
- Operational schema, Alembic migration, import CLI, repositories and services, HTML/HTMX interface, JSON API, local security boundary, and documentation are complete on `feature/fastapi-price-tracking`.
- Next milestone: design immutable SQLite-to-DuckDB ingestion and dbt models for operational observations. Sales ingestion still requires deterministic dates and confirmed row grain.
