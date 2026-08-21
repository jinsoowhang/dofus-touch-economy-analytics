# FastAPI Item Search and Price Tracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local FastAPI website that imports the private cost and recipe exports, searches items, records append-only lot prices, and recalculates crafting cost, profit, and ROI.

**Architecture:** SQLite is the operational database for the FastAPI application; SQLAlchemy repositories and services isolate persistence and business rules from HTML and JSON routers. Jinja and a vendored HTMX asset provide the local browser UI, while DuckDB and dbt remain the downstream analytical layer and receive no request-time writes.

**Tech Stack:** Python 3.12, uv, FastAPI 0.141.1, SQLAlchemy 2.0.51, Alembic 1.19.0, SQLite, Jinja 3.1.6, HTMX 2.0.10, Uvicorn 0.51.0, Pydantic 2, Pytest, Ruff, dbt Core, dbt-duckdb, and DuckDB.

---

## Working rules

- Execute in an isolated worktree created with `using-git-worktrees`.
- Use test-driven development for every behavior: write the focused test, observe the expected failure, add the minimum implementation, then rerun the focused and regression checks.
- Read `notes/FastAPI Item Search and Price Tracking Design.md` before each task and preserve its single-user, loopback-only scope.
- Use `uv`, never `pip`.
- Never print, commit, or copy real CSV rows into tracked fixtures. Tests use synthetic data only.
- Never run dbt directly without `DO_NOT_TRACK=1`; `scripts/check.sh` already exports it.
- Stage files intentionally and make the exact atomic commit listed for each task.
- After every task: run the task's focused tests, `uv run ruff check` on changed Python, `git diff --check`, and the public-file policy.

## Dependency decisions

These exact application releases were verified from their official PyPI project pages on 2026-08-20:

- FastAPI `0.141.1`
- SQLAlchemy `2.0.51`
- Alembic `1.19.0`
- Uvicorn `0.51.0`
- Jinja2 `3.1.6`
- python-multipart `0.0.32`
- HTTPX `0.28.1` for FastAPI `TestClient`

Vendor stable HTMX `2.0.10` from `https://cdn.jsdelivr.net/npm/htmx.org@2.0.10/`.

- `dist/htmx.min.js` SHA-256: `71ea67185bfa8c98c39d31717c6fce5d852370fcdfd129db4543774d3145c0de`
- `LICENSE` SHA-256: `d3d2456f76414f2456104660ebd65aff1c04cd7966b942bdabd63f3cdb316a38`

## Planned file map

```text
alembic.ini                                      Alembic command configuration
migrations/env.py                               migration environment wired to settings
migrations/script.py.mako                       Alembic revision template
migrations/versions/0001_operational_schema.py  initial SQLite schema
data/app/README.md                               ignored application database boundary
data/reports/README.md                           ignored import-report boundary
docs/adr/0002-use-sqlite-for-operational-state.md
src/dofus_touch_economy/
  __init__.py                                    package marker
  app.py                                         FastAPI application factory
  cli.py                                         import and local-server entry points
  config.py                                      environment-backed local settings
  database.py                                    engine, pragmas, sessions, base
  models.py                                      SQLAlchemy operational schema
  schemas.py                                     validated commands and JSON responses
  normalization.py                               deterministic item-name normalization
  importers/contracts.py                         CSV contract parsing
  importers/service.py                           idempotent database import
  repositories/catalog.py                       item, recipe, and search queries
  repositories/prices.py                        observation queries and persistence
  services/catalog.py                            item-detail read model
  services/pricing.py                            price commands and calculations
  routers/api.py                                 `/api/v1` endpoints
  routers/web.py                                 HTML and HTMX endpoints
  templates/...                                  server-rendered pages and fragments
  static/app.css                                 responsive local UI
  static/htmx.min.js                             vendored HTMX 2.0.10
  static/htmx-LICENSE                            vendored upstream license
tests/python/
  conftest.py                                    temporary SQLite fixtures
  fixtures/*.csv                                 synthetic import fixtures
  test_config_database.py
  test_migrations.py
  test_models.py
  test_normalization.py
  test_import_contracts.py
  test_import_service.py
  test_pricing.py
  test_catalog_service.py
  test_api.py
  test_web.py
  test_cli.py
```

## Task 1: Add packaged FastAPI tooling and local-state safety boundaries

**Files:**

- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `.gitignore`
- Modify: `scripts/check_public_files.py`
- Modify: `tests/python/test_check_public_files.py`
- Create: `data/app/README.md`
- Create: `data/reports/README.md`
- Delete: `src/README.md`
- Create: `src/dofus_touch_economy/__init__.py`
- Create: `tests/python/test_package.py`

- [ ] **Step 1: Extend the public-file policy tests first**

Add allowed placeholders and rejected local application artifacts:

```python
def test_allows_public_repository_files() -> None:
    paths = [
        "README.md",
        ".env.example",
        "data/app/README.md",
        "data/raw/README.md",
        "data/reports/README.md",
        "data/samples/example.csv",
        "data/warehouse/README.md",
        "models/staging/stg_source__items.sql",
    ]
    assert find_forbidden_tracked_paths(paths) == []


def test_rejects_application_state() -> None:
    paths = [
        "data/app/dofus_touch.sqlite3",
        "data/app/dofus_touch.sqlite3-wal",
        "data/app/dofus_touch.sqlite3-shm",
        "data/reports/import-report.json",
        "nested/LOCAL.DB",
    ]
    assert find_forbidden_tracked_paths(paths) == sorted(paths)
```

- [ ] **Step 2: Run the focused policy test and observe failure**

Run:

```bash
uv run pytest tests/python/test_check_public_files.py -v
```

Expected: the new allowed READMEs are reported forbidden or the application database/report paths are not rejected.

- [ ] **Step 3: Implement the local-state rules**

Update the checker constants:

```python
FORBIDDEN_PREFIXES = (
    "data/app/",
    "data/raw/",
    "data/reports/",
    "data/warehouse/",
    "dbt_packages/",
    "logs/",
    "skill-observations/",
    "target/",
)
ALLOWED_PATHS = {
    ".env.example",
    "data/app/README.md",
    "data/raw/README.md",
    "data/reports/README.md",
    "data/warehouse/README.md",
}
FORBIDDEN_SUFFIXES = (
    ".db",
    ".db-shm",
    ".db-wal",
    ".duckdb",
    ".duckdb.wal",
    ".sqlite",
    ".sqlite-shm",
    ".sqlite-wal",
    ".sqlite3",
    ".sqlite3-shm",
    ".sqlite3-wal",
    ".xlsx",
)
```

Add matching `.gitignore` rules while preserving the two tracked READMEs:

```gitignore
data/app/**
!data/app/README.md
data/reports/**
!data/reports/README.md
*.db
*.db-shm
*.db-wal
*.sqlite
*.sqlite-shm
*.sqlite-wal
*.sqlite3
*.sqlite3-shm
*.sqlite3-wal
```

The README files must say application databases and import reports are generated,
local, and never committed.

- [ ] **Step 4: Add exact application dependencies and package metadata**

Use `uv add` so `pyproject.toml` and `uv.lock` change together:

```bash
uv add \
  'alembic==1.19.0' \
  'fastapi==0.141.1' \
  'jinja2==3.1.6' \
  'python-multipart==0.0.32' \
  'sqlalchemy==2.0.51' \
  'uvicorn==0.51.0'
uv add --dev 'httpx==0.28.1'
```

Remove the `[tool.uv] package = false` setting and add:

```toml
[build-system]
requires = ["uv_build>=0.12.5,<0.13"]
build-backend = "uv_build"

[tool.uv.build-backend]
module-name = "dofus_touch_economy"
```

Create `src/dofus_touch_economy/__init__.py` with:

```python
"""Dofus Touch economy application."""
```

- [ ] **Step 5: Prove the package installs**

Create `tests/python/test_package.py`:

```python
def test_package_imports() -> None:
    import dofus_touch_economy

    assert dofus_touch_economy.__doc__ == "Dofus Touch economy application."
```

Run:

```bash
uv sync --locked --all-groups
uv run pytest tests/python/test_package.py tests/python/test_check_public_files.py -v
uv run python scripts/check_public_files.py
```

Expected: package import and all public-file tests pass.

- [ ] **Step 6: Commit**

```bash
git add -- pyproject.toml uv.lock .gitignore scripts/check_public_files.py \
  tests/python/test_check_public_files.py tests/python/test_package.py \
  data/app/README.md data/reports/README.md \
  src/README.md src/dofus_touch_economy/__init__.py
git diff --cached --check
git commit -m "build: add FastAPI application toolchain"
```

## Task 2: Add deterministic settings and SQLite session management

**Files:**

- Create: `src/dofus_touch_economy/config.py`
- Create: `src/dofus_touch_economy/database.py`
- Create: `tests/python/test_config_database.py`

- [ ] **Step 1: Write failing configuration and pragma tests**

```python
from pathlib import Path

from sqlalchemy import text

from dofus_touch_economy.config import Settings
from dofus_touch_economy.database import create_engine_for_url


def test_settings_default_to_local_application_state(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DOFUS_PROJECT_ROOT", str(tmp_path))
    monkeypatch.delenv("DOFUS_APP_DATABASE_PATH", raising=False)
    monkeypatch.delenv("DOFUS_MARKET_CONTEXT", raising=False)

    settings = Settings.from_env()

    assert settings.database_path == tmp_path / "data/app/dofus_touch.sqlite3"
    assert settings.market_context == "unspecified"
    assert settings.allowed_hosts == ("127.0.0.1", "localhost")


def test_sqlite_engine_enables_integrity_pragmas(tmp_path: Path) -> None:
    engine = create_engine_for_url(f"sqlite+pysqlite:///{tmp_path / 'app.sqlite3'}")
    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
        assert connection.execute(text("PRAGMA busy_timeout")).scalar_one() == 5000
```

- [ ] **Step 2: Run tests and observe import failure**

```bash
uv run pytest tests/python/test_config_database.py -v
```

Expected: collection fails because `config` and `database` do not exist.

- [ ] **Step 3: Implement settings**

`config.py` must define an immutable `Settings` dataclass with:

```python
@dataclass(frozen=True)
class Settings:
    project_root: Path
    database_path: Path
    market_context: str
    allowed_hosts: tuple[str, ...]

    @property
    def database_url(self) -> str:
        return f"sqlite+pysqlite:///{self.database_path}"

    @classmethod
    def from_env(cls) -> "Settings":
        default_root = Path(__file__).resolve().parents[2]
        project_root = Path(os.environ.get("DOFUS_PROJECT_ROOT", default_root)).resolve()
        configured_path = Path(
            os.environ.get("DOFUS_APP_DATABASE_PATH", "data/app/dofus_touch.sqlite3")
        )
        database_path = (
            configured_path if configured_path.is_absolute() else project_root / configured_path
        ).resolve()
        market_context = os.environ.get("DOFUS_MARKET_CONTEXT", "unspecified").strip()
        if not market_context:
            raise ValueError("DOFUS_MARKET_CONTEXT must not be empty")
        allowed_hosts = tuple(
            host.strip()
            for host in os.environ.get(
                "DOFUS_ALLOWED_HOSTS", "127.0.0.1,localhost"
            ).split(",")
            if host.strip()
        )
        if not allowed_hosts:
            raise ValueError("DOFUS_ALLOWED_HOSTS must contain at least one host")
        return cls(project_root, database_path, market_context, allowed_hosts)
```

This keeps the configured default deterministic even when a command is launched outside the repository directory.

- [ ] **Step 4: Implement the database boundary**

`database.py` must expose:

```python
class Base(DeclarativeBase):
    pass


def create_engine_for_url(database_url: str) -> Engine:
    database_path = database_url.removeprefix("sqlite+pysqlite:///")
    if database_path != ":memory:":
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def configure_sqlite(dbapi_connection: sqlite3.Connection, _: object) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        if database_path != ":memory:":
            cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
```

- [ ] **Step 5: Run focused and regression tests**

```bash
uv run pytest tests/python/test_config_database.py -v
uv run ruff check src/dofus_touch_economy tests/python/test_config_database.py
```

Expected: both tests pass.

- [ ] **Step 6: Commit**

```bash
git add -- src/dofus_touch_economy/config.py \
  src/dofus_touch_economy/database.py tests/python/test_config_database.py
git diff --cached --check
git commit -m "feat: add SQLite application settings"
```

## Task 3: Define the operational schema and initial migration

**Files:**

- Create: `src/dofus_touch_economy/models.py`
- Create: `alembic.ini`
- Create: `migrations/env.py`
- Create: `migrations/script.py.mako`
- Create: `migrations/versions/0001_operational_schema.py`
- Create: `tests/python/test_models.py`
- Create: `tests/python/test_migrations.py`

- [ ] **Step 1: Write failing model-constraint tests**

Tests must create all metadata in an in-memory SQLite engine and assert:

```python
def test_price_observation_rejects_nonpositive_lot_quantity(session) -> None:
    item = Item(display_name="Iron", normalized_name="iron", identity_category="ore")
    session.add(item)
    session.flush()
    session.add(
        PriceObservation(
            item_id=item.id,
            lot_quantity=0,
            total_price=100,
            observed_at=datetime.now(UTC),
            market_context="Dodge",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()


def test_recipe_ingredient_position_is_unique(session) -> None:
    recipe = make_recipe(session)
    session.add_all(
        [
            RecipeIngredient(recipe_id=recipe.id, position=1, raw_name="A", normalized_name="a", quantity=1),
            RecipeIngredient(recipe_id=recipe.id, position=1, raw_name="B", normalized_name="b", quantity=1),
        ]
    )
    with pytest.raises(IntegrityError):
        session.commit()
```

- [ ] **Step 2: Run and observe missing-model failure**

```bash
uv run pytest tests/python/test_models.py -v
```

Expected: collection fails because `models` does not exist.

- [ ] **Step 3: Implement all SQLAlchemy models**

Use SQLAlchemy 2 typed mappings and define exactly these tables and constraints:

| Model | Required persisted fields and constraints |
|---|---|
| `ImportBatch` | integer PK, UUID unique, dataset, filename, checksum, counts, status, started/completed timestamps, unique dataset+checksum |
| `SourceRecord` | PK, batch FK cascade, one-based row number, raw JSON text, status, validation messages JSON text, unique batch+row |
| `Item` | PK, UUID unique, display name, normalized name indexed, nullable category, non-null `identity_category`, timestamps, unique normalized name+identity category |
| `SourceItemName` | PK, source record FK cascade, source field, non-null position (`0` for non-ingredient fields, `1..8` for ingredients), raw and normalized names, nullable item FK, resolution status, unique record+field+position |
| `Recipe` | PK, UUID unique, crafted item FK, profession, source record FK unique, timestamps |
| `RecipeIngredient` | PK, recipe FK cascade, position, nullable item FK, raw and normalized names, positive quantity, unique recipe+position |
| `PriceObservation` | monotonic PK, UUID unique, item FK, positive lot quantity and total price, observed/recorded timestamps, market context, note, source default `manual`, nullable invalidation timestamp/reason |

Use `ondelete="RESTRICT"` for canonical item references and `ondelete="CASCADE"` only for import-owned and recipe-owned child rows. Use database check constraints for positive price/quantity and a check that invalidation timestamp and reason are either both null or both present.

- [ ] **Step 4: Configure Alembic and generate the initial revision**

`migrations/env.py` must import `Base`, import `models` so metadata is registered, replace the config URL with `Settings.from_env().database_url`, and support online and offline migrations.

Run:

```bash
uv run alembic revision --autogenerate -m "create operational schema"
```

Rename the generated file to `migrations/versions/0001_operational_schema.py`, set `revision = "0001"`, and inspect it to confirm all seven tables, FKs, unique constraints, checks, and indexes match the models.

- [ ] **Step 5: Test upgrade and downgrade from an empty file**

`test_migrations.py` must set `DOFUS_APP_DATABASE_PATH` to a temporary file and run:

```python
subprocess.run(["uv", "run", "alembic", "upgrade", "head"], check=True, env=env)
assert set(inspect(engine).get_table_names()) == {
    "alembic_version",
    "import_batches",
    "items",
    "price_observations",
    "recipe_ingredients",
    "recipes",
    "source_item_names",
    "source_records",
}
subprocess.run(["uv", "run", "alembic", "downgrade", "base"], check=True, env=env)
assert inspect(engine).get_table_names() == []
```

Run:

```bash
uv run pytest tests/python/test_models.py tests/python/test_migrations.py -v
```

- [ ] **Step 6: Commit**

```bash
git add -- alembic.ini migrations src/dofus_touch_economy/models.py \
  tests/python/test_models.py tests/python/test_migrations.py
git diff --cached --check
git commit -m "feat: add operational database schema"
```

## Task 4: Implement deterministic normalization and pricing calculations

**Files:**

- Create: `src/dofus_touch_economy/normalization.py`
- Create: `src/dofus_touch_economy/services/__init__.py`
- Create: `src/dofus_touch_economy/services/pricing.py`
- Create: `tests/python/test_normalization.py`
- Create: `tests/python/test_pricing.py`

- [ ] **Step 1: Write failing normalization tests**

```python
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  Gobball   Wool ", "gobball wool"),
        ("ÉCAFLIP", "écaflip"),
        ("Iron\tOre", "iron ore"),
    ],
)
def test_normalize_item_name(raw: str, expected: str) -> None:
    assert normalize_item_name(raw) == expected


def test_normalize_item_name_rejects_blank() -> None:
    with pytest.raises(ValueError, match="must not be blank"):
        normalize_item_name("  ")
```

- [ ] **Step 2: Write failing calculation tests**

```python
def test_calculates_complete_recipe_metrics() -> None:
    metrics = calculate_recipe_metrics(
        crafted_item_price=Decimal("125"),
        ingredients=[
            IngredientPrice(quantity=2, unit_price=Decimal("10")),
            IngredientPrice(quantity=3, unit_price=Decimal("20")),
        ],
    )
    assert metrics.recipe_cost == Decimal("80")
    assert metrics.profit == Decimal("45")
    assert metrics.roi == Decimal("0.5625")
    assert metrics.is_complete is True


def test_missing_price_never_becomes_zero() -> None:
    metrics = calculate_recipe_metrics(
        crafted_item_price=Decimal("125"),
        ingredients=[IngredientPrice(quantity=2, unit_price=None)],
    )
    assert metrics.recipe_cost is None
    assert metrics.profit is None
    assert metrics.roi is None
    assert metrics.is_complete is False
```

- [ ] **Step 3: Run and observe import failures**

```bash
uv run pytest tests/python/test_normalization.py tests/python/test_pricing.py -v
```

- [ ] **Step 4: Implement pure functions and dataclasses**

`normalize_item_name` must use `" ".join(raw.split()).casefold()` and reject blank results.

`pricing.py` must define:

```python
@dataclass(frozen=True)
class IngredientPrice:
    quantity: int
    unit_price: Decimal | None


@dataclass(frozen=True)
class RecipeMetrics:
    recipe_cost: Decimal | None
    profit: Decimal | None
    roi: Decimal | None
    is_complete: bool


def unit_price(total_price: int, lot_quantity: int) -> Decimal:
    if total_price <= 0 or lot_quantity <= 0:
        raise ValueError("price and quantity must be positive")
    return Decimal(total_price) / Decimal(lot_quantity)
```

`calculate_recipe_metrics` must return incomplete metrics if any ingredient price is missing, calculate profit only when the crafted item price is present, and return `roi=None` when recipe cost is zero.

- [ ] **Step 5: Run tests and commit**

```bash
uv run pytest tests/python/test_normalization.py tests/python/test_pricing.py -v
git add -- src/dofus_touch_economy/normalization.py \
  src/dofus_touch_economy/services/__init__.py \
  src/dofus_touch_economy/services/pricing.py \
  tests/python/test_normalization.py tests/python/test_pricing.py
git diff --cached --check
git commit -m "feat: add governed pricing calculations"
```

## Task 5: Validate cost and recipe CSV contracts with synthetic fixtures

**Files:**

- Create: `src/dofus_touch_economy/importers/__init__.py`
- Create: `src/dofus_touch_economy/importers/contracts.py`
- Create: `tests/python/fixtures/item_cost_valid.csv`
- Create: `tests/python/fixtures/item_recipes_valid.csv`
- Create: `tests/python/test_import_contracts.py`

- [ ] **Step 1: Create synthetic fixtures**

The cost fixture contains only invented values:

```csv
raw_material,category,price
Synthetic Ore,Ore,"1,000"
Synthetic Fiber,Fiber,500
```

The recipe fixture uses this exact 29-column source header:

```text
recipe_item,profession,raw_material_1,quantity_1,cost_1,raw_material_2,quantity_2,cost_2,raw_material_3,quantity_3,cost_3,raw_material_4,quantity_4,cost_4,raw_material_5,quantity_5,cost_5,raw_material_6,quantity_6,cost_6,raw_material_7,quantity_7,cost_7,raw_material_8,quantity_8,cost_8,total_cost,profit,ROI
```

Its single invented row has `Synthetic Widget` / `Crafting`, ingredient group 1 `Synthetic Ore` / `2` / `20`, ingredient group 2 `Synthetic Fiber` / `3` / `30`, all fields in groups 3 through 8 empty, and trailing values `50` / `25` / `50%`. No real item names or values may appear.

- [ ] **Step 2: Write failing parser tests**

```python
def test_validates_cost_rows(fixture_dir: Path) -> None:
    result = validate_cost_csv(fixture_dir / "item_cost_valid.csv")
    assert result.rejected == []
    assert [row.raw_material for row in result.accepted] == [
        "Synthetic Ore",
        "Synthetic Fiber",
    ]
    assert result.accepted[0].raw_payload["price"] == "1,000"


def test_flattens_populated_recipe_ingredients(fixture_dir: Path) -> None:
    result = validate_recipe_csv(fixture_dir / "item_recipes_valid.csv")
    assert result.rejected == []
    recipe = result.accepted[0]
    assert [(part.position, part.raw_name, part.quantity) for part in recipe.ingredients] == [
        (1, "Synthetic Ore", 2),
        (2, "Synthetic Fiber", 3),
    ]


def test_rejects_mismatched_material_and_quantity(tmp_path: Path) -> None:
    path = write_recipe_fixture(tmp_path, material_1="Synthetic Ore", quantity_1="")
    result = validate_recipe_csv(path)
    assert result.accepted == []
    assert result.rejected[0].messages == (
        "raw_material_1 and quantity_1 must be populated together",
    )
```

- [ ] **Step 3: Run and observe missing-contract failure**

```bash
uv run pytest tests/python/test_import_contracts.py -v
```

- [ ] **Step 4: Implement contract parsing**

`contracts.py` must define immutable `CostRow`, `IngredientRow`, `RecipeRow`, `RejectedRow`, and generic `ValidationResult` dataclasses plus `ContractError`.

Rules:

- Read `utf-8-sig` with `csv.DictReader` and preserve the raw payload.
- Require the exact three cost headers in source order.
- Require the exact 29 recipe headers in source order.
- Treat one-based CSV data row numbers as spreadsheet row `2` onward.
- Require nonblank cost material/category and recipe item/profession.
- For positions 1 through 8, accept both material and quantity blank, or require both.
- Parse quantity after removing commas; require a positive base-10 integer.
- Preserve cost, source-derived totals, profit, and ROI as raw strings.
- File/header/encoding failures raise `ContractError`.
- Row failures return `RejectedRow` without mutating the source file.

- [ ] **Step 5: Run tests and commit**

```bash
uv run pytest tests/python/test_import_contracts.py -v
git add -- src/dofus_touch_economy/importers \
  tests/python/fixtures tests/python/test_import_contracts.py
git diff --cached --check
git commit -m "feat: validate cost and recipe exports"
```

## Task 6: Import validated catalog and recipes idempotently

**Files:**

- Create: `src/dofus_touch_economy/importers/service.py`
- Create: `src/dofus_touch_economy/cli.py`
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Create: `tests/python/conftest.py`
- Create: `tests/python/test_import_service.py`
- Create: `tests/python/test_cli.py`

- [ ] **Step 1: Add temporary database fixtures**

`conftest.py` must provide a file-backed temporary SQLite engine, create all metadata, yield a session factory, and dispose the engine after each test. File-backed tests exercise the same transaction and pragma behavior as the app.

- [ ] **Step 2: Write failing import tests**

Cover these exact behaviors:

```python
def test_import_is_idempotent(session_factory, fixture_dir: Path) -> None:
    service = ImportService(session_factory)
    first = service.import_files(
        fixture_dir / "item_cost_valid.csv",
        fixture_dir / "item_recipes_valid.csv",
    )
    second = service.import_files(
        fixture_dir / "item_cost_valid.csv",
        fixture_dir / "item_recipes_valid.csv",
    )
    assert first.created_batches == 2
    assert second.created_batches == 0
    with session_factory() as session:
        assert session.scalar(select(func.count(Item.id))) == 3
        assert session.scalar(select(func.count(Recipe.id))) == 1
        assert session.scalar(select(func.count(RecipeIngredient.id))) == 2


def test_ambiguous_exact_name_remains_unresolved(session_factory, synthetic_files) -> None:
    synthetic_files.write_cost_rows(
        [("Shared Name", "Ore", "1"), ("Shared Name", "Fiber", "2")]
    )
    synthetic_files.write_recipe(ingredient="Shared Name", quantity="1")
    ImportService(session_factory).import_files(*synthetic_files.paths)
    with session_factory() as session:
        ingredient = session.scalar(select(RecipeIngredient))
        source_name = session.scalar(
            select(SourceItemName).where(SourceItemName.source_field == "raw_material_1")
        )
        assert ingredient.item_id is None
        assert source_name.resolution_status == "ambiguous"
```

Also assert source raw payloads and rejected rows are stored, item-cost price never creates a `PriceObservation`, and changed checksums create new batches without duplicating existing canonical identities.

- [ ] **Step 3: Run and observe missing-service failure**

```bash
uv run pytest tests/python/test_import_service.py tests/python/test_cli.py -v
```

- [ ] **Step 4: Implement the import service**

The service must:

1. Hash each file with SHA-256.
2. Validate both file-level contracts before opening a write transaction, so a missing file, invalid header, or encoding error leaves the database unchanged.
3. Return an existing successful batch as a no-op.
4. Store every accepted and rejected raw row in `source_records`.
5. For cost rows, identify items by normalized name plus normalized category.
6. For crafted items, reuse the sole exact-name candidate. With no candidate, create the category-empty canonical identity. With multiple candidates, reuse an existing category-empty candidate or create one when none exists.
7. For ingredients, reuse the sole exact-name candidate, create a category-empty candidate when none exists, and leave the link unresolved when multiple candidates exist (including when one candidate has an empty category).
8. Persist `source_item_names` for crafted and ingredient fields.
9. Expand recipes to ordered ingredients.
10. Store both new batch records, accepted/rejected source rows, application rows, counts, and `completed` statuses in one transaction. Any unexpected failure rolls back the entire import invocation before re-raising.

Expose an `ImportSummary` containing created batch count, accepted count, rejected count, warning count, and JSON-serializable conflict details.

- [ ] **Step 5: Implement the CLI**

`import_main()` must use `argparse` with defaults:

```text
--cost-file data/raw/item_cost.csv
--recipe-file data/raw/item_recipes.csv
--report-file data/reports/latest-import.json
```

It must run the service, write a UTF-8 indented JSON report, print only counts and report location, and return exit code `1` when rejected rows exist. It must never print raw rows or item names.

Register only the implemented import command at this stage, then refresh the lock:

```toml
[project.scripts]
dofus-import = "dofus_touch_economy.cli:import_main"
```

```bash
uv lock
```

- [ ] **Step 6: Run focused tests and commit**

```bash
uv run pytest tests/python/test_import_service.py tests/python/test_cli.py -v
git add -- pyproject.toml uv.lock src/dofus_touch_economy/importers/service.py \
  src/dofus_touch_economy/cli.py tests/python/conftest.py \
  tests/python/test_import_service.py tests/python/test_cli.py
git diff --cached --check
git commit -m "feat: import catalog and recipes"
```

## Task 7: Add catalog and price-observation application services

**Files:**

- Create: `src/dofus_touch_economy/schemas.py`
- Create: `src/dofus_touch_economy/repositories/__init__.py`
- Create: `src/dofus_touch_economy/repositories/catalog.py`
- Create: `src/dofus_touch_economy/repositories/prices.py`
- Create: `src/dofus_touch_economy/services/catalog.py`
- Modify: `src/dofus_touch_economy/services/pricing.py`
- Create: `tests/python/test_catalog_service.py`
- Modify: `tests/python/test_pricing.py`

- [ ] **Step 1: Write failing current-price and invalidation tests**

Define local `dt(year, month, day)` and `make_observation(...)` test helpers in `test_pricing.py`; `dt` returns a UTC-aware `datetime`, and the observation helper defaults `recorded_at` to one second after `observed_at`.

```python
def test_latest_valid_observation_uses_observed_then_recorded_order(session, item) -> None:
    older_recorded_later = make_observation(
        session, item, total_price=100, observed_at=dt(2026, 8, 19), recorded_at=dt(2026, 8, 20)
    )
    newer_observed = make_observation(
        session, item, total_price=120, observed_at=dt(2026, 8, 20), recorded_at=dt(2026, 8, 19)
    )
    session.commit()
    assert PriceRepository(session).latest_valid(item.id, "Dodge").id == newer_observed.id
    assert older_recorded_later.id != newer_observed.id


def test_invalidation_restores_previous_valid_price(session, item) -> None:
    previous = make_observation(session, item, total_price=100)
    current = make_observation(session, item, total_price=120)
    session.commit()
    service = PriceService(session, market_context="Dodge")
    service.invalidate(current.uuid, "Mistyped market price")
    assert service.current_for_item(item.id).observation_uuid == previous.uuid


def test_cannot_invalidate_twice(session, item) -> None:
    observation = make_observation(session, item)
    session.commit()
    service = PriceService(session, market_context="Dodge")
    service.invalidate(observation.uuid, "Mistake")
    with pytest.raises(ObservationConflict):
        service.invalidate(observation.uuid, "Again")
```

- [ ] **Step 2: Write failing item-detail tests**

Assert search is normalized substring matching, category disambiguates duplicate names, unresolved ingredients make metrics incomplete, and a fully priced recipe returns exact Decimal values.

- [ ] **Step 3: Implement validated commands and response schemas**

Pydantic models must include:

```python
class PriceObservationCreate(BaseModel):
    lot_quantity: int = Field(gt=0)
    total_price: int = Field(gt=0)
    observed_at: datetime
    note: str | None = Field(default=None, max_length=500)

    @field_validator("observed_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at must include a timezone")
        return value


class InvalidationCreate(BaseModel):
    reason: str = Field(min_length=1, max_length=500)
```

Define JSON response schemas for item summaries, current price, observations, recipe ingredients, recipe metrics, and item detail. Serialize Decimal values as strings so API consumers never receive binary floats.

- [ ] **Step 4: Implement repositories and services**

- `CatalogRepository.search(query, limit=50)` normalizes the query and returns display name/category ordered by normalized name then category.
- `CatalogRepository.get_by_uuid` eagerly loads recipe and ingredient rows.
- `PriceRepository.latest_valid` filters item, active market context, and null invalidation, then applies the three-part ordering.
- `PriceRepository.history` returns newest-first observations for the active context.
- `PriceService.record` creates and commits one observation.
- `PriceService.invalidate` atomically sets timestamp and stripped reason, rejecting unknown/already-invalid observations.
- `CatalogService.detail` composes catalog, latest prices, recent history, and governed metrics without exposing ORM models to routers.

Define `ItemNotFound`, `ObservationNotFound`, and `ObservationConflict` application exceptions.

- [ ] **Step 5: Run tests and commit**

```bash
uv run pytest tests/python/test_pricing.py tests/python/test_catalog_service.py -v
git add -- src/dofus_touch_economy/schemas.py \
  src/dofus_touch_economy/repositories \
  src/dofus_touch_economy/services/catalog.py \
  src/dofus_touch_economy/services/pricing.py \
  tests/python/test_pricing.py tests/python/test_catalog_service.py
git diff --cached --check
git commit -m "feat: add item pricing services"
```

## Task 8: Add the FastAPI factory, local security boundary, and read routes

**Files:**

- Create: `src/dofus_touch_economy/app.py`
- Create: `src/dofus_touch_economy/routers/__init__.py`
- Create: `src/dofus_touch_economy/routers/api.py`
- Create: `src/dofus_touch_economy/routers/web.py`
- Create: `src/dofus_touch_economy/templates/base.html`
- Create: `src/dofus_touch_economy/templates/items.html`
- Create: `src/dofus_touch_economy/templates/item_detail.html`
- Create: `src/dofus_touch_economy/templates/fragments/item_results.html`
- Create: `tests/python/test_api.py`
- Create: `tests/python/test_web.py`

- [ ] **Step 1: Write failing app-security tests**

```python
def test_root_redirects_to_items(client: TestClient) -> None:
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/items"


def test_rejects_untrusted_host(client: TestClient) -> None:
    response = client.get("/items", headers={"host": "example.com"})
    assert response.status_code == 400


def test_rejects_cross_origin_mutation(client: TestClient, item) -> None:
    response = client.post(
        f"/api/v1/items/{item.uuid}/price-observations",
        headers={"origin": "https://example.com"},
        json={"lot_quantity": 1, "total_price": 100, "observed_at": "2026-08-20T12:00:00Z"},
    )
    assert response.status_code == 403
```

- [ ] **Step 2: Write failing search and detail route tests**

Assert `/items?q=ore` renders matching synthetic items, `/api/v1/items?q=ore` returns the same UUIDs, unknown detail routes return `404`, and detail HTML visibly labels incomplete recipe cost.

- [ ] **Step 3: Implement the application factory**

`create_app(settings: Settings | None = None, session_factory=None) -> FastAPI` must:

- build settings and the engine/session factory when not injected
- add `TrustedHostMiddleware` with configured hosts
- add a small middleware that rejects unsafe methods when an `Origin` header is present and its authority does not equal the request authority
- mount package static files at `/static` with `check_dir=False`; Task 10 creates and verifies the vendored files before templates reference them
- include web and `/api/v1` routers
- store settings and session factory on `app.state`

Provide a request-scoped session dependency that commits only through services and always closes the session.

- [ ] **Step 4: Implement read-only routers and templates**

- HTML templates extend `base.html`, use Jinja autoescaping, have a visible project title, and display empty/incomplete/error states.
- `/items` accepts `q: str = ""` and caps results at 50. A normal request renders `items.html`; an `HX-Request` renders only `fragments/item_results.html`, which is also included by the full page.
- `/items/{uuid}` renders the composed detail read model.
- `/api/v1/items` and `/api/v1/items/{uuid}` return Pydantic response schemas.
- Application `ItemNotFound` maps to `404` for HTML and JSON.

- [ ] **Step 5: Run tests and commit**

```bash
uv run pytest tests/python/test_api.py tests/python/test_web.py -v
git add -- src/dofus_touch_economy/app.py \
  src/dofus_touch_economy/routers src/dofus_touch_economy/templates \
  tests/python/test_api.py tests/python/test_web.py
git diff --cached --check
git commit -m "feat: add item search website"
```

## Task 9: Add price recording and invalidation over HTML and JSON

**Files:**

- Modify: `src/dofus_touch_economy/routers/api.py`
- Modify: `src/dofus_touch_economy/routers/web.py`
- Modify: `src/dofus_touch_economy/templates/item_detail.html`
- Create: `src/dofus_touch_economy/templates/fragments/price_panel.html`
- Create: `src/dofus_touch_economy/templates/fragments/recipe_metrics.html`
- Modify: `tests/python/test_api.py`
- Modify: `tests/python/test_web.py`

- [ ] **Step 1: Write failing API mutation tests**

```python
def test_records_lot_price_and_returns_recalculated_detail(client, item) -> None:
    response = client.post(
        f"/api/v1/items/{item.uuid}/price-observations",
        json={
            "lot_quantity": 10,
            "total_price": 1250,
            "observed_at": "2026-08-20T12:00:00Z",
            "note": "Manual market check",
        },
    )
    assert response.status_code == 201
    assert response.json()["current_price"]["unit_price"] == "125"


def test_invalidates_observation_and_restores_previous_api_price(client, priced_item) -> None:
    response = client.post(
        f"/api/v1/price-observations/{priced_item.current_uuid}/invalidation",
        json={"reason": "Mistyped price"},
    )
    assert response.status_code == 200
    assert response.json()["current_price"]["observation_uuid"] == priced_item.previous_uuid
```

Also test `422` for nonpositive values/naive timestamps, `404` for unknown UUIDs, and `409` for repeated invalidation.

- [ ] **Step 2: Write failing HTML/HTMX mutation tests**

Post form-encoded data with `HX-Request: true`; assert `200`, fragment HTML, active market context display, updated metrics, inline validation errors, and no full-page navigation requirement.

- [ ] **Step 3: Implement shared mutation routes**

- JSON create returns `201` and the recomposed item detail.
- JSON invalidation returns `200` and recomposed detail.
- HTML create and invalidation parse explicit form fields into the same Pydantic commands and call the same services.
- HTMX success returns the price panel as the main fragment and the recipe metrics fragment with an out-of-band swap targeting `#recipe-metrics`, so both current price/history and calculations update from one mutation.
- Non-HTMX form success redirects to item detail using `303`.
- HTML validation returns status `422` with form errors and preserves safe submitted values.
- Application exceptions map to the specified `404` and `409` statuses.

- [ ] **Step 4: Run tests and commit**

```bash
uv run pytest tests/python/test_api.py tests/python/test_web.py -v
git add -- src/dofus_touch_economy/routers \
  src/dofus_touch_economy/templates tests/python/test_api.py tests/python/test_web.py
git diff --cached --check
git commit -m "feat: record and invalidate item prices"
```

## Task 10: Vendor HTMX, add responsive styling, and complete local commands

**Files:**

- Create: `src/dofus_touch_economy/static/htmx.min.js`
- Create: `src/dofus_touch_economy/static/htmx-LICENSE`
- Create: `src/dofus_touch_economy/static/app.css`
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `src/dofus_touch_economy/templates/base.html`
- Modify: `src/dofus_touch_economy/templates/items.html`
- Modify: `src/dofus_touch_economy/templates/item_detail.html`
- Modify: `src/dofus_touch_economy/cli.py`
- Modify: `tests/python/test_cli.py`
- Create: `tests/python/test_static_assets.py`

- [ ] **Step 1: Write failing asset and CLI tests**

```python
def test_vendored_htmx_has_reviewed_digest() -> None:
    data = resources.files("dofus_touch_economy").joinpath("static/htmx.min.js").read_bytes()
    assert hashlib.sha256(data).hexdigest() == "71ea67185bfa8c98c39d31717c6fce5d852370fcdfd129db4543774d3145c0de"


def test_web_main_binds_loopback(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(uvicorn, "run", lambda *args, **kwargs: calls.append((args, kwargs)))
    assert web_main([]) == 0
    assert calls[0][1]["host"] == "127.0.0.1"
    assert calls[0][1]["factory"] is True
```

- [ ] **Step 2: Download and verify HTMX and its license**

```bash
curl -fsSL https://cdn.jsdelivr.net/npm/htmx.org@2.0.10/dist/htmx.min.js \
  -o src/dofus_touch_economy/static/htmx.min.js
curl -fsSL https://cdn.jsdelivr.net/npm/htmx.org@2.0.10/LICENSE \
  -o src/dofus_touch_economy/static/htmx-LICENSE
sha256sum src/dofus_touch_economy/static/htmx.min.js \
  src/dofus_touch_economy/static/htmx-LICENSE
```

Expected hashes are the two values in the dependency-decision section. Abort rather than committing if either differs.

- [ ] **Step 3: Add the responsive UI**

`base.html` loads only `/static/app.css` and `/static/htmx.min.js`; it has no CDN references. CSS must provide:

- readable light/dark system colors
- centered content with a wide recipe table on desktop
- stacked cards/forms below 720px
- visible focus states
- status colors that are not the only indicator
- numeric alignment for kama values
- an HTMX request indicator

Search should update results after a short input delay using `hx-get="/items"`, `hx-trigger="input changed delay:250ms, search"`, and a dedicated results target while preserving normal form submission.

- [ ] **Step 4: Add the web entry point and local-only CLI**

Add the second project script, then refresh the lock:

```toml
[project.scripts]
dofus-import = "dofus_touch_economy.cli:import_main"
dofus-web = "dofus_touch_economy.cli:web_main"
```

```bash
uv lock
```

`web_main(argv: Sequence[str] | None = None) -> int` accepts `--host`, `--port`, and `--reload`. Default host is `127.0.0.1`; if a non-loopback host is requested, exit with a message explaining that public binding requires a separate security design. Call:

```python
uvicorn.run(
    "dofus_touch_economy.app:create_app",
    factory=True,
    host=args.host,
    port=args.port,
    reload=args.reload,
)
```

- [ ] **Step 5: Run tests and commit**

```bash
uv run pytest tests/python/test_static_assets.py tests/python/test_cli.py tests/python/test_web.py -v
git add -- pyproject.toml uv.lock src/dofus_touch_economy/static src/dofus_touch_economy/templates \
  src/dofus_touch_economy/cli.py tests/python/test_static_assets.py \
  tests/python/test_cli.py tests/python/test_web.py
git diff --cached --check
git commit -m "feat: complete local price tracking UI"
```

## Task 11: Document the operational architecture and developer workflow

**Files:**

- Create: `docs/adr/0002-use-sqlite-for-operational-state.md`
- Modify: `docs/architecture.md`
- Modify: `docs/data-contract.md`
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `.env.example`
- Modify: `scripts/check.sh`
- Modify: `.pre-commit-config.yaml`
- Modify: `.github/workflows/ci.yml`
- Create: `tests/python/test_documented_commands.py`

- [ ] **Step 1: Write failing documentation-command tests**

The test must assert README commands exist as project entry points and that private paths are not required by CI:

```python
def test_documented_entry_points_exist() -> None:
    scripts = tomllib.loads(Path("pyproject.toml").read_text())["project"]["scripts"]
    assert scripts == {
        "dofus-import": "dofus_touch_economy.cli:import_main",
        "dofus-web": "dofus_touch_economy.cli:web_main",
    }


def test_ci_does_not_import_private_data() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text()
    assert "dofus-import" not in workflow
    assert "data/raw" not in workflow
```

- [ ] **Step 2: Write ADR 0002**

Record:

- Context: mutable local price observations are operational state.
- Decision: FastAPI writes SQLite; DuckDB/dbt remain analytical and read operational extracts in a separate milestone.
- Consequences: two ignored databases with different ownership, no request-time DuckDB writes, migrations required, public deployment deferred.

- [ ] **Step 3: Update public and agent documentation**

README must document exact commands:

```bash
uv sync --locked --all-groups
DOFUS_APP_DATABASE_PATH=data/app/dofus_touch.sqlite3 uv run alembic upgrade head
uv run dofus-import
uv run dofus-web
```

Explain that import uses local ignored cost/recipe CSVs, `item_sales.csv` is deferred, the website is loopback-only, imported reference prices are not current observations, and real data is never required by CI.

Architecture must show CSV validation/import to SQLite, FastAPI reads/writes SQLite, and the deferred SQLite-to-DuckDB analytical boundary. Data contract must add operational observation fields and current-price ordering. AGENTS must add migration/import/web/test commands and protect SQLite/report artifacts.

`.env.example` must contain public-safe examples:

```dotenv
DOFUS_APP_DATABASE_PATH=data/app/dofus_touch.sqlite3
DOFUS_MARKET_CONTEXT=unspecified
DOFUS_ALLOWED_HOSTS=127.0.0.1,localhost
```

- [ ] **Step 4: Extend automated verification**

Add this command to `scripts/check.sh` before dbt checks; migration correctness remains covered by the isolated upgrade/downgrade test from Task 3:

```bash
uv run python -m compileall -q src
```

Add equivalent local pre-commit hooks with `pass_filenames: false`. CI continues to run only `./scripts/check.sh` and receives no private data.

- [ ] **Step 5: Run tests and commit**

```bash
uv run pytest tests/python/test_documented_commands.py -v
./scripts/check.sh
DO_NOT_TRACK=1 uv run pre-commit run --all-files
git add -- README.md AGENTS.md .env.example docs/architecture.md \
  docs/data-contract.md docs/adr/0002-use-sqlite-for-operational-state.md \
  scripts/check.sh .pre-commit-config.yaml .github/workflows/ci.yml \
  tests/python/test_documented_commands.py
git diff --cached --check
git commit -m "docs: document local price tracking application"
```

## Task 12: Verify with local data, record the session, and publish

**Files:**

- Modify: `MEMORY.md`
- Create or modify: `notes/Session Notes 2026-08-20.md`

- [ ] **Step 1: Run the full synthetic-data suite first**

```bash
uv sync --locked --all-groups
./scripts/check.sh
DO_NOT_TRACK=1 uv run pre-commit run --all-files
uv run python scripts/check_public_files.py
```

Expected: all tests, migrations, lint, dbt parse, SQLFluff, and public-file checks pass without private CSV access.

- [ ] **Step 2: Create and migrate a disposable ignored local database**

Use an explicit task-scoped path:

```bash
export DOFUS_APP_DATABASE_PATH=data/app/verification.sqlite3
uv run alembic upgrade head
uv run dofus-import --report-file data/reports/verification-import.json
```

Expected: the command reports counts only, creates ignored SQLite/report files, imports `item_cost.csv` and `item_recipes.csv`, and does not read `item_sales.csv`. A nonzero import result caused only by explicitly reported rejected rows must be investigated and reflected accurately; do not claim success until the accepted/rejected behavior matches the design.

- [ ] **Step 3: Run a local application smoke test without exposing it**

Start on loopback in an exec session:

```bash
uv run dofus-web --host 127.0.0.1 --port 8000
```

Verify from another shell:

```bash
curl --fail --silent --show-error http://127.0.0.1:8000/items >/dev/null
```

Stop the server cleanly. Do not bind `0.0.0.0`.

- [ ] **Step 4: Verify local-only state and public history**

```bash
git check-ignore -v \
  data/app/verification.sqlite3 \
  data/reports/verification-import.json \
  data/raw/item_cost.csv \
  data/raw/item_recipes.csv
git ls-files | rg -i '\.(csv|db|sqlite|sqlite3|xlsx)$|(^|/)\.user\.yml$'
git status --short
```

Expected: every local path is ignored; the tracked-file search returns only explicitly allowed synthetic CSV fixtures under `tests/python/fixtures/`; Git status contains only the memory/session-note changes.

- [ ] **Step 5: Update durable memory and session evidence**

`MEMORY.md` must add:

- FastAPI/Jinja/HTMX local website
- SQLite operational state and DuckDB analytical state
- append-only lot price observations and invalidation audit
- item cost/recipe import included, item sales deferred
- exact name normalization and ambiguity policy

The dated session note must record actual verified commands, accepted/rejected import counts, loopback smoke result, expected dbt empty-model warning if it still exists, and the next analytics bridge milestone. Do not include private item names, raw rows, machine-specific paths, or job-practice context.

- [ ] **Step 6: Commit records and rerun final verification**

```bash
git add -- MEMORY.md "notes/Session Notes 2026-08-20.md"
git diff --cached --check
git commit -m "docs: record FastAPI price tracking milestone"
./scripts/check.sh
DO_NOT_TRACK=1 uv run pre-commit run --all-files
git status --short --branch
```

- [ ] **Step 7: Request final branch review and publish only after approval**

Review the complete feature range against the design and this plan. Fix all Critical and Important findings and rerun reviewers. After final approval, merge through the finishing-development-branch workflow, push `main`, and watch GitHub Actions to a successful conclusion.
