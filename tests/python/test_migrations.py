import os
import subprocess
from pathlib import Path

from sqlalchemy import inspect, text

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
    item_columns = {column["name"] for column in inspect(engine).get_columns("items")}
    assert "created_source" in item_columns
    with engine.connect() as connection:
        connection.execute(
            text(
                "INSERT INTO items "
                "(uuid, display_name, normalized_name, category, identity_category, "
                "created_at, updated_at) VALUES "
                "('00000000000000000000000000000001', 'Imported Item', 'imported item', "
                "NULL, '', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
        )
        source = connection.scalar(
            text("SELECT created_source FROM items WHERE normalized_name = 'imported item'")
        )
        assert source == "imported"
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
