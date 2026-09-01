from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any


@dataclass(frozen=True)
class SnapshotColumn:
    name: str
    bigquery_type: str
    required: bool = True


@dataclass(frozen=True)
class OperationalTable:
    name: str
    columns: tuple[SnapshotColumn, ...]


@dataclass(frozen=True)
class SnapshotTable:
    contract: OperationalTable
    rows: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class OperationalSnapshot:
    snapshot_id: str
    extracted_at: datetime
    source_schema_version: str
    tables: tuple[SnapshotTable, ...]

    @property
    def row_counts(self) -> MappingProxyType[str, int]:
        return MappingProxyType({table.contract.name: len(table.rows) for table in self.tables})


def _column(name: str, bigquery_type: str, *, required: bool = True) -> SnapshotColumn:
    return SnapshotColumn(name=name, bigquery_type=bigquery_type, required=required)


OPERATIONAL_TABLES = (
    OperationalTable(
        "import_batches",
        (
            _column("id", "INTEGER"),
            _column("uuid", "STRING"),
            _column("dataset", "STRING"),
            _column("filename", "STRING"),
            _column("checksum", "STRING"),
            _column("accepted_count", "INTEGER"),
            _column("rejected_count", "INTEGER"),
            _column("warning_count", "INTEGER"),
            _column("status", "STRING"),
            _column("started_at", "TIMESTAMP"),
            _column("completed_at", "TIMESTAMP", required=False),
        ),
    ),
    OperationalTable(
        "source_records",
        (
            _column("id", "INTEGER"),
            _column("import_batch_id", "INTEGER"),
            _column("row_number", "INTEGER"),
            _column("raw_payload_json", "STRING"),
            _column("status", "STRING"),
            _column("validation_messages_json", "STRING"),
        ),
    ),
    OperationalTable(
        "items",
        (
            _column("id", "INTEGER"),
            _column("uuid", "STRING"),
            _column("display_name", "STRING"),
            _column("normalized_name", "STRING"),
            _column("category", "STRING", required=False),
            _column("identity_category", "STRING"),
            _column("created_source", "STRING"),
            _column("icon_source_url", "STRING", required=False),
            _column("weight", "INTEGER", required=False),
            _column("touch_catalog_status", "STRING", required=False),
            _column("touch_catalog_checked_at", "TIMESTAMP", required=False),
            _column("touch_catalog_exclusion_reason", "STRING", required=False),
            _column("created_at", "TIMESTAMP"),
            _column("updated_at", "TIMESTAMP"),
        ),
    ),
    OperationalTable(
        "source_item_names",
        (
            _column("id", "INTEGER"),
            _column("source_record_id", "INTEGER"),
            _column("source_field", "STRING"),
            _column("position", "INTEGER"),
            _column("raw_name", "STRING"),
            _column("normalized_name", "STRING"),
            _column("item_id", "INTEGER", required=False),
            _column("resolution_status", "STRING"),
        ),
    ),
    OperationalTable(
        "recipes",
        (
            _column("id", "INTEGER"),
            _column("uuid", "STRING"),
            _column("crafted_item_id", "INTEGER"),
            _column("profession", "STRING"),
            _column("source_record_id", "INTEGER"),
            _column("created_at", "TIMESTAMP"),
            _column("updated_at", "TIMESTAMP"),
        ),
    ),
    OperationalTable(
        "recipe_ingredients",
        (
            _column("id", "INTEGER"),
            _column("recipe_id", "INTEGER"),
            _column("position", "INTEGER"),
            _column("item_id", "INTEGER", required=False),
            _column("raw_name", "STRING"),
            _column("normalized_name", "STRING"),
            _column("quantity", "INTEGER"),
        ),
    ),
    OperationalTable(
        "price_observations",
        (
            _column("id", "INTEGER"),
            _column("uuid", "STRING"),
            _column("item_id", "INTEGER"),
            _column("lot_quantity", "INTEGER"),
            _column("total_price", "INTEGER"),
            _column("observed_at", "TIMESTAMP"),
            _column("recorded_at", "TIMESTAMP"),
            _column("market_context", "STRING"),
            _column("note", "STRING", required=False),
            _column("source", "STRING"),
            _column("invalidated_at", "TIMESTAMP", required=False),
            _column("invalidation_reason", "STRING", required=False),
        ),
    ),
    OperationalTable(
        "sale_listings",
        (
            _column("id", "INTEGER"),
            _column("uuid", "STRING"),
            _column("item_id", "INTEGER"),
            _column("price_observation_id", "INTEGER", required=False),
            _column("lot_quantity", "INTEGER"),
            _column("asking_price", "INTEGER", required=False),
            _column("selling_started_at", "TIMESTAMP"),
            _column("date_sold", "TIMESTAMP", required=False),
            _column("recipe_cost_at_sale", "NUMERIC", required=False),
            _column("listing_source", "STRING", required=False),
            _column("listing_capture_uuid", "STRING", required=False),
            _column("sale_source", "STRING", required=False),
            _column("sale_capture_uuid", "STRING", required=False),
        ),
    ),
)


def extract_operational_snapshot(database_path: Path) -> OperationalSnapshot:
    resolved_path = database_path.expanduser().resolve()
    if not resolved_path.is_file():
        raise FileNotFoundError(f"operational database does not exist: {resolved_path}")

    connection = sqlite3.connect(f"file:{resolved_path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        schema_version = _read_schema_version(connection)
        snapshot_tables = tuple(
            _read_table(connection, contract) for contract in OPERATIONAL_TABLES
        )
        snapshot_id = _content_hash(schema_version, snapshot_tables)
    finally:
        connection.rollback()
        connection.close()

    return OperationalSnapshot(
        snapshot_id=snapshot_id,
        extracted_at=datetime.now(UTC),
        source_schema_version=schema_version,
        tables=snapshot_tables,
    )


def _read_schema_version(connection: sqlite3.Connection) -> str:
    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    if "alembic_version" not in tables:
        raise ValueError("operational database is missing alembic_version")
    row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
    if row is None or not row[0]:
        raise ValueError("operational database has no Alembic schema version")
    return str(row[0])


def _read_table(
    connection: sqlite3.Connection,
    contract: OperationalTable,
) -> SnapshotTable:
    actual_columns = {row[1] for row in connection.execute(f'PRAGMA table_info("{contract.name}")')}
    expected_columns = {column.name for column in contract.columns}
    if actual_columns != expected_columns:
        missing = sorted(expected_columns - actual_columns)
        unexpected = sorted(actual_columns - expected_columns)
        raise ValueError(
            f"{contract.name} schema does not match the analytical contract; "
            f"missing={missing}, unexpected={unexpected}"
        )

    selected_columns = ", ".join(f'"{column.name}"' for column in contract.columns)
    raw_rows = connection.execute(
        f'SELECT {selected_columns} FROM "{contract.name}" ORDER BY "id"'
    ).fetchall()
    rows = tuple(
        {column.name: _normalize_value(row[column.name], column) for column in contract.columns}
        for row in raw_rows
    )
    return SnapshotTable(contract=contract, rows=rows)


def _normalize_value(value: Any, column: SnapshotColumn) -> Any:
    if value is None:
        if column.required:
            raise ValueError(f"required column {column.name} contains NULL")
        return None
    if column.bigquery_type == "TIMESTAMP":
        return _normalize_timestamp(value)
    return value


def _normalize_timestamp(value: Any) -> str:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _content_hash(
    schema_version: str,
    tables: tuple[SnapshotTable, ...],
) -> str:
    digest = hashlib.sha256()
    digest.update(f"operational-schema:{schema_version}\n".encode())
    for table in tables:
        digest.update(f"table:{table.contract.name}\n".encode())
        for row in table.rows:
            digest.update(
                json.dumps(
                    row,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode("utf-8")
            )
            digest.update(b"\n")
    return digest.hexdigest()
