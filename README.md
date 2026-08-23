# Dofus Touch Economy Analytics

Local-first economy tracking and hosted analytics for player-observed Dofus Touch
items, recipes, market prices, crafting economics, and Sales listings.

This is an unofficial fan project and is not affiliated with, endorsed by, or sponsored by Ankama. Dofus Touch and related names belong to their respective owners.

The implemented FastAPI website runs locally against SQLite. It imports catalog and
recipe structure, records append-only market observations and Sales activity, and
calculates crafting cost, profit, and ROI. An immutable snapshot loader publishes
normalized operational data to BigQuery, where dbt builds documented and tested
staging, intermediate, and mart models. DuckDB and dbt Core remain the local parse
and CI path.

The BigQuery and free dbt Developer environments are operational for both development
and production. Publication is intentionally manual: website changes remain in
SQLite until the snapshot loader runs, and dbt models refresh only after a subsequent
`dbt build`. Raw CSVs, SQLite databases, and credentials must never enter Git.

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
 FastAPI + Jinja + HTMX    immutable snapshot loader
                                  |
                                  v
                         BigQuery raw tables
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

Item icons are an ignored local cache and are not stored inside the SQLite database.
If the database was copied or restored without `data/app/item_icons/`, rebuild the
cache before refreshing the website:

```bash
uv run dofus-fetch-icons
```

The command may report catalog entries whose public upstream image is unavailable;
successfully downloaded icons remain usable.

The live catalog sync stores each matched item's official carrying weight in pods
from the Dofus Touch `realWeight` field. It also replaces an imported catch-all
**Resource** display category with a more specific exact-match type such as **Skin**,
**Plant**, **Flower**, or **Seed**. Run it after migrating a restored or older
database:

```bash
uv run dofus-sync-catalog
```

Zero is a valid upstream weight. Items without an unambiguous live catalog match
retain an unknown weight instead of being assigned zero. Category refinement prefers
the current Dofus Touch type, then uses an exact DofusDB legacy-item match only when
all returned candidates agree. Missing or conflicting matches remain **Resource**;
the original normalized import category remains the stable identity key.

Search is normalized and case-insensitive. When no catalog item matches, the page shows
advisory spelling suggestions and an **Add item** form. Manually added items can receive
price observations immediately. A later import reuses the same normalized
name/category identity, or enriches a sole uncategorized manual item without changing
its UUID or price history.

The top navigation contains **Item**, **Sales**, and **BigQuery Sync**. Hovering over
or selecting **Item** opens its **Item Search**, **Recipes**, and **Recipe Calculator**
submenu. **Sales** opens **Sales Activity** and **Out of Stock Items**.
The item page lists the full catalog in 100-row alphabetical pages beneath the search
field, including category, weight, latest unit price, and observation time.
Typing filters the table by item name. Clicking any row opens item detail, where a new
audited price observation can be recorded.

The Recipes page lists the latest recipe for each craftable item with its profession,
standard required profession level, current item price, recipe cost, profit, and ROI.
It supports item, category, profession, profitability, and a single dual-handle
profession-level range filter with synchronized numeric endpoints, plus sorting on
every displayed field. Craftable Items are returned in 100-row pages, and each row can
be added to the browser-local Recipe Calculator cart. Current Price is editable
directly in each row; Enter or leaving the field appends a price observation and
refreshes the calculated economics without creating a Sales listing. Required
profession level follows the standard Dofus Touch ingredient-slot unlocks: levels 1,
10, 20, 40, 60, 80, and 100 for increasing recipe sizes through eight ingredients.
Item detail shows the same level beside the recipe profession.
Ingredient rows show calendar days since the current price observation and classify
it as **Missing price**, **Current price**, or **Stale price** at seven days old.

The Recipe Calculator accepts multiple craftable items and a craft quantity for each.
Items remain in its browser-local cart until removed, while row checkboxes, **Select
all**, and **Select none** control which cart items are included in the next calculation.
It combines shared ingredients into one shopping list with category, total quantity,
total weight, current unit price, extended cost, price freshness status, and consuming
recipes. Summary cards report complete total weight when every weight
is known, otherwise the known subtotal remains explicit alongside the incomplete
state. Price coverage and complete or known-cost totals remain independent of weight
coverage.
Resolved ingredient unit prices are editable directly in the shopping list; Enter or
leaving the field appends a price observation, restores the previous scroll position,
and recalculates every affected total.
Missing prices and unresolved ingredients remain explicit rather than becoming zero.

Every data-bearing table supports sorting by its displayed data columns. Selection,
calculator, and mutation-only Action columns are intentionally excluded from sorting.

Manual item names are whitespace-normalized and title-cased. The add form recognizes
common equipment types from a complete final word, so `chouquish belt` previews and
creates `Chouquish Belt` in category `Belt`. The category remains editable as an
explicit override.

The import command validates both CSV contracts before writing, stores accepted and rejected source-row provenance in SQLite, and writes an ignored report to `data/reports/latest-import.json`. A repeated dataset checksum is a no-op. A result containing rejected rows returns a nonzero exit code while retaining valid rows from the completed transaction.

In **Currently Selling**, row actions restore the previous scroll position after the
page refreshes. Checkboxes support selecting individual rows or the full table, then
marking the selection as sold or deleting it as one atomic action. Bulk deletion
requires confirmation. The collapsed **Filter Items** panel below the add form
narrows Sales listings by item name,
category, status, price, profit, or Pacific activity date while preserving the
filters through sorting and row actions. Each item-detail page shows how many of that
item are actively listed and how many have been sold through the application; the
count cards link to the corresponding filtered Sales table.
**Out of Stock Items** lists each item with completed Sales history but no active
listing, together with its latest sale, current price, recipe cost, estimated profit,
and an Add-to-Calculator action when a recipe is available.

## Publish analytics updates

The **BigQuery Sync** page runs the same guarded loader in the background and shows
timestamped dataset and table progress. It permits only one run at a time and never
accepts browser-supplied commands, project IDs, dataset IDs, or credential values.
The local web server must have valid Google Application Default Credentials.

First preview the next immutable snapshot without contacting Google:

```bash
uv run dofus-load-bigquery --dry-run
```

Then publish the normalized SQLite state to both `dofus_dev` and `dofus_prod` in the
`US` multi-region:

```bash
uv run dofus-load-bigquery \
  --project-id=claude-projects-489306 \
  --location=US
```

After the loader completes, run `dbt build` in the dbt Studio development environment
to refresh `dofus_dev_*`. When a manual production deployment job is configured, run
it only after reviewing the development build and its cost. No recurring sync or
scheduled production job is configured.

See [docs/operational-bigquery-ingestion.md](docs/operational-bigquery-ingestion.md)
for authentication, sidebar navigation, verification, and retry behavior.

## Data boundary

Private raw exports, operational databases, import reports, DuckDB files, and generated artifacts remain local and Git-ignored. Only invented synthetic fixtures are committed, and CI never requires private data. The normalized operational rows may exist privately in BigQuery after the contracted loader publishes an immutable snapshot.

- `item_cost.csv` and `item_recipes.csv` are in application-import scope.
- `item_sales.csv` remains deferred until dates and row grain are deterministic;
  BigQuery Sales data comes only from normalized application listings.
- Imported `item_cost.price` values are preserved as reconciliation provenance; they are not treated as timestamped current market observations.
- Current prices come only from valid manual lot observations recorded through the application for its configured market context.

See [docs/data-contract.md](docs/data-contract.md) for exact source and operational contracts.

## Repository structure

- `src/dofus_touch_economy/`: FastAPI application, import contracts, services, repositories, templates, and vendored static assets
- `migrations/`: Alembic operational-database migrations
- `models/`: dbt staging, intermediate, and marts layers for operational snapshots
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
uv run dofus-load-bigquery --dry-run
DO_NOT_TRACK=1 uv run dbt debug --profiles-dir .
DO_NOT_TRACK=1 uv run dbt parse --profiles-dir .
DO_NOT_TRACK=1 uv run sqlfluff lint models analyses
uv run python scripts/check_public_files.py
```

Run the complete local and CI-equivalent sequence with `./scripts/check.sh`.

## Hosted analytics

See [docs/dbt-cloud-bigquery-setup.md](docs/dbt-cloud-bigquery-setup.md) for the
BigQuery IAM, dbt connection, GitHub, environment, verification, and cost-control
steps. See [docs/operational-bigquery-ingestion.md](docs/operational-bigquery-ingestion.md)
for snapshot loading and sidebar-based verification. Full guarded dbt builds have
passed in both development and production; local DuckDB checks remain the public,
credential-free CI path.

## Licensing

The repository's MIT license covers original code and documentation only. It does not grant rights to source data, game content, names, artwork, or other third-party material. Vendored HTMX retains its upstream license. Raw data remains local unless redistribution rights are established.
