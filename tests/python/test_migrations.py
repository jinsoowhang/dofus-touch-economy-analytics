import os
import subprocess
from pathlib import Path

from sqlalchemy import inspect

from dofus_touch_economy.config import Settings
from dofus_touch_economy.database import create_engine_for_url


def test_initial_migration_upgrades_and_downgrades_empty_database(tmp_path: Path) -> None:
    database_path = tmp_path / "migrations.sqlite3"
    environment = os.environ.copy()
    environment["DOFUS_APP_DATABASE_PATH"] = str(database_path)

    subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        check=True,
        env=environment,
    )

    engine = create_engine_for_url(
        Settings.from_env().database_url.set(database=str(database_path))
    )
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
    engine.dispose()

    subprocess.run(
        ["uv", "run", "alembic", "downgrade", "base"],
        check=True,
        env=environment,
    )

    downgraded_engine = create_engine_for_url(
        Settings.from_env().database_url.set(database=str(database_path))
    )
    assert inspect(downgraded_engine).get_table_names() == ["alembic_version"]
    downgraded_engine.dispose()
