# Dofus Touch Economy Analytics

Analytics engineering for player-observed item prices, crafting economics, and sales behavior in Dofus Touch.

This is an unofficial fan project and is not affiliated with, endorsed by, or sponsored by Ankama. Dofus Touch and related names belong to their respective owners.

Status: this repository currently provides a reproducible dbt and DuckDB foundation only. Ingestion waits on deterministic ISO dates or approved source parsing rules, and domain modeling additionally waits on final row-grain and duplicate-cost decisions.

Architecture:

```text
private CSV exports
    -> contract validation and DuckDB loading
    -> dbt staging / intermediate / marts
    -> governed metrics / optional semantic layer and BI
```

See [docs/architecture.md](docs/architecture.md) for component boundaries and flow details.

## Local setup

Requirements:

- WSL or Linux
- Git
- `uv`

Commands:

```bash
uv python install 3.12
uv sync --locked --all-groups
./scripts/check.sh
```

## Data boundary

Private raw exports stay local and Git-ignored under these canonical names:

- `data/raw/item_sales.csv`
- `data/raw/item_recipes.csv`
- `data/raw/item_cost.csv`

Only synthetic fixtures with clear provenance belong in `data/samples/`. See [docs/data-contract.md](docs/data-contract.md) for the source contract and current blockers.

## Repository structure

- `models/`: dbt staging, intermediate, and marts layers
- `analyses/`: dbt analyses and exploratory SQL
- `tests/dbt/`: dbt singular test SQL
- `tests/python/`: Python unit tests
- `src/`: future ingestion and validation code
- `data/`: ignored raw data, synthetic samples, and ignored local warehouse files
- `docs/`: architecture, source contracts, and ADRs
- `notes/`: design decisions, plans, and session notes

## Development commands

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
DO_NOT_TRACK=1 uv run dbt debug --profiles-dir .
DO_NOT_TRACK=1 uv run dbt parse --profiles-dir .
DO_NOT_TRACK=1 uv run sqlfluff lint models analyses
uv run python scripts/check_public_files.py
```

For the full local verification sequence, run `./scripts/check.sh`.

## Licensing

The repository's MIT license covers original code and documentation only. It does not grant rights to source data, game content, names, artwork, or other third-party material. Raw data remains local unless redistribution rights are established.
