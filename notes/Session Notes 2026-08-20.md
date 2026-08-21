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
