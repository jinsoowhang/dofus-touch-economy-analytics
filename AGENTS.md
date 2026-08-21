# AGENTS.md

## What This Is

This repository is a public, reproducible analytics project for player-observed Dofus Touch economy data. The current milestone establishes local tooling, public-safe boundaries, and documentation; ingestion and analytical models start only after source contracts are deterministic.

## Session Workflow

- Invoke task-observer at the start of any task-oriented session.
- Before behavioral changes, read `MEMORY.md`, the latest session notes in `notes/`, and any relevant docs that define current constraints.
- Treat notes, design docs, and session logs in `notes/` as part of the working record.
- At session end, update `MEMORY.md` with durable project decisions and append or create a dated session note.
- If `MEMORY.md` or session notes do not exist yet, follow this workflow when creating them instead of assuming they already exist.

## Where Things Live

- `dbt_project.yml` keeps the dbt project at the repository root.
- `models/staging/`, `models/intermediate/`, and `models/marts/` define the transformation layers.
- `analyses/` holds dbt analyses.
- `tests/dbt/` holds singular dbt tests.
- `tests/python/` holds Python tests.
- `src/` is reserved for future contract validation and DuckDB loading code.
- `data/raw/` is for local raw exports only and is ignored except for its README.
- `data/samples/` is for synthetic public fixtures with clear provenance.
- `data/warehouse/` is for ignored local DuckDB artifacts.
- `docs/` holds architecture, source contracts, and ADRs.
- `notes/` holds design, plans, and session notes.

## Commands

- Install Python 3.12 if needed: `uv python install 3.12`
- Sync the environment: `uv sync --locked --all-groups`
- Run the full local check sequence: `./scripts/check.sh`
- Run Python lint: `uv run ruff check .`
- Check Python formatting: `uv run ruff format --check .`
- Run Python tests: `uv run pytest`
- Validate the dbt profile: `DO_NOT_TRACK=1 uv run dbt debug --profiles-dir .`
- Parse the dbt project: `DO_NOT_TRACK=1 uv run dbt parse --profiles-dir .`
- Lint SQL: `DO_NOT_TRACK=1 uv run sqlfluff lint models analyses`
- Enforce public-file policy: `uv run python scripts/check_public_files.py`

## Conventions

- Use Python 3.12 and `uv`; add or update Python dependencies through `uv`, not `pip`.
- Keep naming in `snake_case` where the ecosystem supports it.
- Match dbt naming conventions:
  - staging: `stg_<source>__<entity>`
  - intermediate: `int_<description>`
  - dimensions: `dim_<entity>`
  - facts: `fct_<process>`
- Document the grain of every model explicitly.
- Keep parsing and source-standardization in staging.
- Keep business rules and reusable domain transformations in intermediate and marts.
- Prefer portable SQL. If DuckDB-specific logic is necessary, isolate it in focused macros or ingestion code.
- Use generic schema tests for keys and relationships, and singular dbt tests for invariants that need custom assertions.
- Preserve raw values as observed. Report parsing issues or validation failures explicitly instead of silently repairing them.
- Make the smallest change that satisfies the task, keep commits atomic, and avoid unrelated refactors.

## Verification

- Run `./scripts/check.sh` before claiming completion.
- If a smaller change does not justify the full script, still run the relevant focused checks and explain what was not run.
- Use `git diff --check` before staging and `git diff --cached --check` before committing.
- Confirm `git status --short` does not include tracked raw data, local warehouses, secrets, or observer files.

## Ignore or Avoid

- Keep `data/raw/` private. Put local exports there under the canonical names documented in `data/raw/README.md`.
- Keep DuckDB files, spreadsheets, credentials, `.env` files, `.user.yml`, task-observer logs, and `.worktrees/` out of Git by using the existing ignored local paths.
- Publish only synthetic sample data unless redistribution rights are documented.
- Preserve source values exactly as collected. If a contract is unclear, stop and document the blocker rather than guessing.
- Do not automate game-client actions or external collection workflows unless the user gives explicit authorization.

## Deeper Docs

- [README.md](README.md) for the public project overview and local setup.
- [docs/architecture.md](docs/architecture.md) for system boundaries and flow.
- [docs/data-contract.md](docs/data-contract.md) for source requirements and blockers.
- [docs/adr/0001-use-dbt-and-duckdb.md](docs/adr/0001-use-dbt-and-duckdb.md) for the stack decision.
- `notes/Dofus Touch Economy Analytics Scaffold Design.md` for the approved scaffold design.
- `notes/Dofus Touch Economy Analytics Scaffold Implementation Plan.md` for the implementation task map.
