# Session Notes 2026-08-20

## Context

Established the public and local analytics foundation for Dofus Touch economy work using three private CSV exports kept outside Git.

## Work Completed

- Approved the scaffold design and recorded the implementation boundaries needed for atomic follow-on work.
- Confirmed Git and commit structure expectations for atomic changes.
- Established local-only boundaries for `data/warehouse`, secrets, generated artifacts, and other ignored machine-specific files.
- Standardized the canonical local raw source names as `data/raw/item_sales.csv`, `data/raw/item_recipes.csv`, and `data/raw/item_cost.csv`.
- Synced the locked Python 3.12 `uv` environment.
- Verified an empty dbt Core project targeting local DuckDB.
- Verified Python, SQL, dbt, public-file, pre-commit, and CI-facing checks.
- Confirmed the public architecture, contract, ADR, setup, and agent-facing documentation is in place for the scaffold.

## Decisions

- Keep raw source data out of Git.
- Use dbt Core with DuckDB before any hosted infrastructure.
- Do not add placeholder models.
- Do not infer missing years from abbreviated source dates.
- Preserve source-derived costs, profits, differences, and ROI for reconciliation, then recompute analytical measures under governed logic.
- Normalize wide recipe structures only after ingestion contracts are defined and enforced.

## Verification

- `uv sync --locked --all-groups` completed successfully.
- `./scripts/check.sh` passed, including formatting, Python tests, dbt debug, dbt parse, and the public-file policy check.
- `uv run pre-commit run --all-files` passed, including Ruff, pytest, dbt parse, and the public file policy hook.
- `git check-ignore -v` confirmed the local CSV files, DuckDB artifact, local secret/config files, skill-observation log, and analytics worktree are ignored as intended.
- Confirmed the three canonical raw CSV files exist locally and remain ignored.
- Confirmed `.user.yml` is ignored and untracked.
- Confirmed the repository and analytics worktree contain no `.xlsx` files, no `.xlsx` or `.user.yml` paths are tracked, and public tracked files contain no private machine paths.
- dbt emitted the expected warnings for unused model configuration paths because no models have been added yet.

## Next Step

Obtain deterministic ISO dates through a source re-export or an explicitly approved parsing rule, then implement test-driven source validation and immutable DuckDB loading before adding dbt models.

## FastAPI Website Implementation Checkpoint

### What was done

1. Approved and committed the FastAPI item-search and price-tracking design and implementation plan.
2. Created the isolated `feature/fastapi-price-tracking` worktree.
3. Packaged the Python application and pinned FastAPI, SQLAlchemy, Alembic, Jinja, Uvicorn, and HTTPX dependencies.
4. Protected SQLite databases, WAL/SHM/rollback journals, and import reports from Git.
5. Added deterministic application settings and the SQLite engine/session boundary using test-driven development.

### Current state

- Task 1 passed implementation, spec, and quality review.
- Task 2 has seven focused tests passing and passed spec review.
- Task 2 quality review identified two portability concerns requiring investigation: threaded in-memory SQLite pooling and database filenames containing `?`.
- No Task 3 work has started.
- The feature and main worktrees are clean; the feature remains unmerged and unpushed.

### Next steps

1. Reproduce the two Task 2 quality concerns with failing tests.
2. Fix confirmed issues and complete quality re-review.
3. Begin Task 3: SQLAlchemy operational schema and Alembic migration.
