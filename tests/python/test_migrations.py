import os
import subprocess
from pathlib import Path

from sqlalchemy import inspect, text

from dofus_touch_economy.config import Settings
from dofus_touch_economy.database import create_engine_for_url


def test_migrations_preserve_populated_database_and_downgrade(tmp_path: Path) -> None:
    database_path = tmp_path / "migrations.sqlite3"
    environment = os.environ.copy()
    environment["DOFUS_APP_DATABASE_PATH"] = str(database_path)

    subprocess.run(
        ["uv", "run", "alembic", "upgrade", "0001"],
        check=True,
        env=environment,
    )

    engine = create_engine_for_url(
        Settings.from_env().database_url.set(database=str(database_path))
    )
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO items "
                "(uuid, display_name, normalized_name, category, identity_category, "
                "created_at, updated_at) VALUES "
                "('00000000000000000000000000000001', 'Imported Item', 'imported item', "
                "NULL, '', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO price_observations "
                "(uuid, item_id, lot_quantity, total_price, observed_at, recorded_at, "
                "market_context, note, source, invalidated_at, invalidation_reason) VALUES "
                "('00000000000000000000000000000002', 1, 1, 100, CURRENT_TIMESTAMP, "
                "CURRENT_TIMESTAMP, 'Dodge', NULL, 'manual', NULL, NULL)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO items "
                "(uuid, display_name, normalized_name, category, identity_category, "
                "created_at, updated_at) VALUES "
                "('00000000000000000000000000000003', 'Violet Arrow Helmet', "
                "'violet arrow helmet', 'Hat', 'hat', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
        )
    engine.dispose()

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
        "sale_listings",
        "source_item_names",
        "source_records",
    }
    item_columns = {column["name"] for column in inspect(engine).get_columns("items")}
    sale_columns = {column["name"] for column in inspect(engine).get_columns("sale_listings")}
    assert "created_source" in item_columns
    assert "icon_source_url" in item_columns
    assert "weight" in item_columns
    assert "touch_catalog_status" in item_columns
    assert "touch_catalog_checked_at" in item_columns
    assert "touch_catalog_exclusion_reason" in item_columns
    assert "asking_price" in sale_columns
    assert "recipe_cost_at_sale" in sale_columns
    with engine.connect() as connection:
        source = connection.scalar(
            text("SELECT created_source FROM items WHERE normalized_name = 'imported item'")
        )
        assert source == "imported"
        assert (
            connection.scalar(
                text("SELECT weight FROM items WHERE normalized_name = 'imported item'")
            )
            is None
        )
        assert (
            connection.scalar(
                text(
                    "SELECT touch_catalog_status FROM items WHERE normalized_name = 'imported item'"
                )
            )
            is None
        )
        violet_status = connection.execute(
            text(
                "SELECT touch_catalog_status, touch_catalog_checked_at, "
                "touch_catalog_exclusion_reason FROM items "
                "WHERE normalized_name = 'violet arrow helmet'"
            )
        ).one()
        assert violet_status[0] == "excluded"
        assert violet_status[1] is not None
        assert "absent" in violet_status[2]
        assert connection.scalar(text("SELECT count(*) FROM price_observations")) == 1
        assert connection.scalar(text("SELECT count(*) FROM sale_listings")) == 1
        assert connection.scalar(text("SELECT asking_price FROM sale_listings")) == 100
        assert connection.scalar(text("SELECT recipe_cost_at_sale FROM sale_listings")) is None
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
