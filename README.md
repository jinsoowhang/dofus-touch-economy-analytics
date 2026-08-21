# Dofus Touch Economy Analytics

Local-first item search, market-price tracking, and analytics engineering for a player-observed Dofus Touch economy.

This is an unofficial fan project and is not affiliated with, endorsed by, or sponsored by Ankama. Dofus Touch and related names belong to their respective owners.

The current application milestone provides a loopback-only FastAPI website backed by SQLite. It imports catalog and recipe structure from local CSV exports, records append-only market observations, and calculates crafting cost, profit, and ROI. DuckDB and dbt remain the downstream analytical layer; the SQLite-to-DuckDB bridge and analytical models are deferred.

```text
ignored item_cost.csv + item_recipes.csv
                    |
                    v
          validation and import report
                    |
                    v
       ignored SQLite operational database
          |                       |
          v                       v
 FastAPI + Jinja + HTMX    deferred DuckDB ingestion
                                  |
                                  v
                     dbt staging / intermediate / marts
```

See [docs/architecture.md](docs/architecture.md) for component ownership and data-flow details.

## Local setup

Requirements:

- WSL or Linux
- Git
- `uv`

Install the locked Python 3.12 environment:

```bash
uv python install 3.12
uv sync --locked --all-groups
```

Place the private exports at `data/raw/item_cost.csv` and `data/raw/item_recipes.csv`, then migrate, import, and start the application:

```bash
DOFUS_APP_DATABASE_PATH=data/app/dofus_touch.sqlite3 uv run alembic upgrade head
uv run dofus-import
uv run dofus-web
```

The website binds to `127.0.0.1:8000` by default. Public or non-loopback binding is rejected because it requires a separate authentication, authorization, CSRF, HTTPS, secrets, and production-database design.

Search is normalized and case-insensitive. When no catalog item matches, the page shows
advisory spelling suggestions and an **Add item** form. Manually added items can receive
price observations immediately. A later import reuses the same normalized
name/category identity, or enriches a sole uncategorized manual item without changing
its UUID or price history.

Manual item names are whitespace-normalized and title-cased. The add form recognizes
common equipment types from a complete final word, so `chouquish belt` previews and
creates `Chouquish Belt` in category `Belt`. The category remains editable as an
explicit override.

The import command validates both CSV contracts before writing, stores accepted and rejected source-row provenance in SQLite, and writes an ignored report to `data/reports/latest-import.json`. A repeated dataset checksum is a no-op. A result containing rejected rows returns a nonzero exit code while retaining valid rows from the completed transaction.

## Data boundary

Private raw exports, operational databases, import reports, DuckDB files, and generated artifacts remain local and Git-ignored. Only invented synthetic fixtures are committed, and CI never requires private data.

- `item_cost.csv` and `item_recipes.csv` are in application-import scope.
- `item_sales.csv` remains deferred until dates and row grain are deterministic.
- Imported `item_cost.price` values are preserved as reconciliation provenance; they are not treated as timestamped current market observations.
- Current prices come only from valid manual lot observations recorded through the application for its configured market context.

See [docs/data-contract.md](docs/data-contract.md) for exact source and operational contracts.

## Repository structure

- `src/dofus_touch_economy/`: FastAPI application, import contracts, services, repositories, templates, and vendored static assets
- `migrations/`: Alembic operational-database migrations
- `models/`: deferred dbt staging, intermediate, and marts layers
- `analyses/`: dbt analyses and exploratory SQL
- `tests/dbt/`: dbt singular test SQL
- `tests/python/`: synthetic application and repository tests
- `data/raw/`: ignored source exports
- `data/app/`: ignored SQLite operational state
- `data/reports/`: ignored import reports
- `data/warehouse/`: ignored DuckDB analytical state
- `docs/`: architecture, contracts, and ADRs
- `notes/`: approved designs, implementation plans, and session notes

## Development commands

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run python -m compileall -q src
DO_NOT_TRACK=1 uv run dbt debug --profiles-dir .
DO_NOT_TRACK=1 uv run dbt parse --profiles-dir .
DO_NOT_TRACK=1 uv run sqlfluff lint models analyses
uv run python scripts/check_public_files.py
```

Run the complete local and CI-equivalent sequence with `./scripts/check.sh`.

## Licensing

The repository's MIT license covers original code and documentation only. It does not grant rights to source data, game content, names, artwork, or other third-party material. Vendored HTMX retains its upstream license. Raw data remains local unless redistribution rights are established.
