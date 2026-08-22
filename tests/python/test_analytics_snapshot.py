from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from google.api_core.exceptions import NotFound
from sqlalchemy import text

from dofus_touch_economy.analytics_snapshot import (
    OPERATIONAL_TABLES,
    extract_operational_snapshot,
)
from dofus_touch_economy.bigquery_loader import BigQuerySnapshotLoader
from dofus_touch_economy.cli import load_bigquery_main
from dofus_touch_economy.database import Base, create_engine_for_url, create_session_factory
from dofus_touch_economy.models import Item


def _create_database(path: Path) -> None:
    engine = create_engine_for_url(f"sqlite+pysqlite:///{path}")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        connection.execute(text("INSERT INTO alembic_version (version_num) VALUES ('0005')"))
    factory = create_session_factory(engine)
    with factory() as session:
        session.add(
            Item(
                display_name="Synthetic Ore",
                normalized_name="synthetic ore",
                category="Ore",
                identity_category="ore",
                created_at=datetime(2026, 8, 22, tzinfo=UTC),
                updated_at=datetime(2026, 8, 22, tzinfo=UTC),
            )
        )
        session.commit()
    engine.dispose()


def test_snapshot_is_complete_and_content_addressed(tmp_path: Path) -> None:
    database_path = tmp_path / "application.sqlite3"
    _create_database(database_path)

    first = extract_operational_snapshot(database_path)
    second = extract_operational_snapshot(database_path)

    assert first.snapshot_id == second.snapshot_id
    assert first.source_schema_version == "0005"
    assert tuple(first.row_counts) == tuple(table.name for table in OPERATIONAL_TABLES)
    assert first.row_counts["items"] == 1
    assert sum(first.row_counts.values()) == 1
    items = next(table for table in first.tables if table.contract.name == "items")
    assert items.rows[0]["display_name"] == "Synthetic Ore"
    assert items.rows[0]["created_at"] == "2026-08-22T00:00:00Z"


def test_snapshot_id_changes_when_operational_data_changes(tmp_path: Path) -> None:
    database_path = tmp_path / "application.sqlite3"
    _create_database(database_path)
    before = extract_operational_snapshot(database_path)

    engine = create_engine_for_url(f"sqlite+pysqlite:///{database_path}")
    with engine.begin() as connection:
        connection.execute(text("UPDATE items SET display_name = 'Changed Ore'"))
    engine.dispose()

    after = extract_operational_snapshot(database_path)

    assert after.snapshot_id != before.snapshot_id


def test_snapshot_rejects_uncontracted_schema_changes(tmp_path: Path) -> None:
    database_path = tmp_path / "application.sqlite3"
    _create_database(database_path)
    engine = create_engine_for_url(f"sqlite+pysqlite:///{database_path}")
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE items ADD COLUMN uncontracted TEXT"))
    engine.dispose()

    with pytest.raises(ValueError, match="items schema does not match"):
        extract_operational_snapshot(database_path)


def test_bigquery_cli_dry_run_needs_no_credentials(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database_path = tmp_path / "application.sqlite3"
    _create_database(database_path)
    monkeypatch.setenv("DOFUS_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("DOFUS_APP_DATABASE_PATH", str(database_path))

    result = load_bigquery_main(["--dry-run"])

    assert result == 0
    output = capsys.readouterr().out
    assert "schema=0005" in output
    assert "items=1" in output
    assert "dry-run: no BigQuery changes made" in output
    assert "Synthetic Ore" not in output


class _CompletedJob:
    def __init__(self, rows=None, output_rows: int | None = None) -> None:
        self._rows = rows or []
        self.output_rows = output_rows

    def result(self):
        return self._rows


class _FakeDataset:
    location = "US"


class _FakeBigQueryClient:
    def __init__(self) -> None:
        self.tables = {}
        self.rows = {}

    def get_dataset(self, _dataset_ref):
        return _FakeDataset()

    def get_table(self, table_id):
        if table_id not in self.tables:
            raise NotFound("missing")
        return self.tables[table_id]

    def create_table(self, table):
        table_id = f"{table.project}.{table.dataset_id}.{table.table_id}"
        self.tables[table_id] = table
        return table

    def query(self, query, *, job_config, location):
        assert location == "US"
        snapshot_id = job_config.query_parameters[0].value
        table_id = query.split("`")[1]
        if query.startswith("SELECT"):
            rows = (
                [object()]
                if any(row["snapshot_id"] == snapshot_id for row in self.rows.get(table_id, []))
                else []
            )
            return _CompletedJob(rows)
        self.rows[table_id] = [
            row for row in self.rows.get(table_id, []) if row["_snapshot_id"] != snapshot_id
        ]
        return _CompletedJob()

    def load_table_from_json(self, rows, table_id, *, location, job_config):
        assert location == "US"
        assert job_config.write_disposition == "WRITE_APPEND"
        self.rows.setdefault(table_id, []).extend(rows)
        return _CompletedJob(output_rows=len(rows))


def test_bigquery_loader_publishes_manifest_last_and_is_idempotent(tmp_path: Path) -> None:
    database_path = tmp_path / "application.sqlite3"
    _create_database(database_path)
    snapshot = extract_operational_snapshot(database_path)
    client = _FakeBigQueryClient()
    loader = BigQuerySnapshotLoader("example-project", "US", client=client)

    first = loader.load(snapshot, ("dofus_dev",))
    second = loader.load(snapshot, ("dofus_dev",))

    assert first[0].loaded is True
    assert second[0].loaded is False
    assert len(client.rows["example-project.dofus_dev.raw_items"]) == 1
    manifests = client.rows["example-project.dofus_dev.raw_snapshot_manifest"]
    assert len(manifests) == 1
    assert manifests[0]["snapshot_id"] == snapshot.snapshot_id
