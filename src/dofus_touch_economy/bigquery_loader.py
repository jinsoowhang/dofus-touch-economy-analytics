from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from google.api_core.exceptions import NotFound
from google.cloud import bigquery

from dofus_touch_economy.analytics_snapshot import OperationalSnapshot, SnapshotColumn

MANIFEST_TABLE = "raw_snapshot_manifest"
_DATASET_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class DatasetLoadResult:
    dataset: str
    snapshot_id: str
    loaded: bool
    row_count: int


class BigQuerySnapshotLoader:
    def __init__(
        self,
        project_id: str,
        location: str,
        *,
        maximum_bytes_billed: int = 1_000_000_000,
        client: bigquery.Client | None = None,
        progress: Callable[[str], None] | None = None,
    ) -> None:
        if "`" in project_id:
            raise ValueError("project ID contains an invalid character")
        if maximum_bytes_billed <= 0:
            raise ValueError("maximum_bytes_billed must be positive")
        self.project_id = project_id
        self.location = location
        self.maximum_bytes_billed = maximum_bytes_billed
        self.client = client or bigquery.Client(project=project_id)
        self._progress = progress or (lambda _message: None)

    def load(
        self,
        snapshot: OperationalSnapshot,
        datasets: tuple[str, ...],
    ) -> tuple[DatasetLoadResult, ...]:
        if not datasets:
            raise ValueError("at least one BigQuery dataset is required")
        if len(set(datasets)) != len(datasets):
            raise ValueError("BigQuery datasets must be unique")
        return tuple(self._load_dataset(snapshot, dataset) for dataset in datasets)

    def _load_dataset(
        self,
        snapshot: OperationalSnapshot,
        dataset: str,
    ) -> DatasetLoadResult:
        self._validate_dataset(dataset)
        self._progress(f"dataset={dataset} status=checking")
        self._require_dataset(dataset)
        self._ensure_manifest_table(dataset)
        total_row_count = sum(snapshot.row_counts.values())
        if self._manifest_exists(dataset, snapshot.snapshot_id):
            self._progress(f"dataset={dataset} status=already-loaded")
            return DatasetLoadResult(
                dataset=dataset,
                snapshot_id=snapshot.snapshot_id,
                loaded=False,
                row_count=total_row_count,
            )

        for snapshot_table in snapshot.tables:
            table_name = f"raw_{snapshot_table.contract.name}"
            schema = self._raw_schema(snapshot_table.contract.columns)
            self._ensure_table(dataset, table_name, schema)
            self._delete_snapshot_rows(dataset, table_name, snapshot.snapshot_id)
            rows = [
                {
                    **row,
                    "_snapshot_id": snapshot.snapshot_id,
                    "_extracted_at": snapshot.extracted_at.isoformat(),
                }
                for row in snapshot_table.rows
            ]
            self._progress(f"dataset={dataset} table={table_name} status=loading rows={len(rows)}")
            self._append_rows(dataset, table_name, schema, rows)

        self._progress(f"dataset={dataset} status=publishing-manifest")
        self._append_manifest(dataset, snapshot, total_row_count)
        self._progress(f"dataset={dataset} status=complete")
        return DatasetLoadResult(
            dataset=dataset,
            snapshot_id=snapshot.snapshot_id,
            loaded=True,
            row_count=total_row_count,
        )

    def _validate_dataset(self, dataset: str) -> None:
        if not _DATASET_PATTERN.fullmatch(dataset):
            raise ValueError(f"invalid BigQuery dataset ID: {dataset}")

    def _require_dataset(self, dataset: str) -> None:
        dataset_ref = f"{self.project_id}.{dataset}"
        resolved = self.client.get_dataset(dataset_ref)
        if (resolved.location or "").casefold() != self.location.casefold():
            raise ValueError(
                f"dataset {dataset_ref} is in {resolved.location}, expected {self.location}"
            )

    def _ensure_manifest_table(self, dataset: str) -> None:
        self._ensure_table(dataset, MANIFEST_TABLE, self._manifest_schema())

    def _ensure_table(
        self,
        dataset: str,
        table_name: str,
        schema: list[bigquery.SchemaField],
    ) -> None:
        table_id = self._table_id(dataset, table_name)
        try:
            table = self.client.get_table(table_id)
        except NotFound:
            table = bigquery.Table(table_id, schema=schema)
            table.time_partitioning = bigquery.TimePartitioning(
                type_=bigquery.TimePartitioningType.DAY,
                field="_extracted_at" if table_name != MANIFEST_TABLE else "extracted_at",
            )
            table.clustering_fields = [
                "_snapshot_id" if table_name != MANIFEST_TABLE else "snapshot_id"
            ]
            self.client.create_table(table)
            return

        expected = [(field.name, field.field_type, field.mode) for field in schema]
        actual = [(field.name, field.field_type, field.mode) for field in table.schema]
        if actual != expected:
            raise ValueError(
                f"BigQuery table {table_id} does not match the loader schema; "
                "review the schema before loading"
            )

    def _manifest_exists(self, dataset: str, snapshot_id: str) -> bool:
        query = (
            f"SELECT 1 FROM `{self._table_id(dataset, MANIFEST_TABLE)}` "
            "WHERE snapshot_id = @snapshot_id LIMIT 1"
        )
        rows = self.client.query(
            query,
            location=self.location,
            job_config=self._query_config(snapshot_id),
        ).result()
        return next(iter(rows), None) is not None

    def _delete_snapshot_rows(
        self,
        dataset: str,
        table_name: str,
        snapshot_id: str,
    ) -> None:
        query = (
            f"DELETE FROM `{self._table_id(dataset, table_name)}` WHERE _snapshot_id = @snapshot_id"
        )
        self.client.query(
            query,
            location=self.location,
            job_config=self._query_config(snapshot_id),
        ).result()

    def _append_rows(
        self,
        dataset: str,
        table_name: str,
        schema: list[bigquery.SchemaField],
        rows: list[dict[str, Any]],
    ) -> None:
        if not rows:
            return
        job_config = bigquery.LoadJobConfig(
            schema=schema,
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        )
        job = self.client.load_table_from_json(
            rows,
            self._table_id(dataset, table_name),
            location=self.location,
            job_config=job_config,
        )
        job.result()
        if job.output_rows != len(rows):
            raise RuntimeError(
                f"BigQuery loaded {job.output_rows} of {len(rows)} rows into {table_name}"
            )

    def _append_manifest(
        self,
        dataset: str,
        snapshot: OperationalSnapshot,
        total_row_count: int,
    ) -> None:
        row = {
            "snapshot_id": snapshot.snapshot_id,
            "extracted_at": snapshot.extracted_at.isoformat(),
            "source_schema_version": snapshot.source_schema_version,
            "total_row_count": total_row_count,
            "table_counts_json": json.dumps(
                dict(snapshot.row_counts),
                separators=(",", ":"),
                sort_keys=True,
            ),
        }
        self._append_rows(
            dataset,
            MANIFEST_TABLE,
            self._manifest_schema(),
            [row],
        )

    def _query_config(self, snapshot_id: str) -> bigquery.QueryJobConfig:
        return bigquery.QueryJobConfig(
            maximum_bytes_billed=self.maximum_bytes_billed,
            query_parameters=[bigquery.ScalarQueryParameter("snapshot_id", "STRING", snapshot_id)],
        )

    def _table_id(self, dataset: str, table_name: str) -> str:
        return f"{self.project_id}.{dataset}.{table_name}"

    @staticmethod
    def _raw_schema(columns: tuple[SnapshotColumn, ...]) -> list[bigquery.SchemaField]:
        schema = [
            bigquery.SchemaField(
                column.name,
                column.bigquery_type,
                mode="REQUIRED" if column.required else "NULLABLE",
            )
            for column in columns
        ]
        schema.extend(
            (
                bigquery.SchemaField("_snapshot_id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("_extracted_at", "TIMESTAMP", mode="REQUIRED"),
            )
        )
        return schema

    @staticmethod
    def _manifest_schema() -> list[bigquery.SchemaField]:
        return [
            bigquery.SchemaField("snapshot_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("extracted_at", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("source_schema_version", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("total_row_count", "INTEGER", mode="REQUIRED"),
            bigquery.SchemaField("table_counts_json", "STRING", mode="REQUIRED"),
        ]
