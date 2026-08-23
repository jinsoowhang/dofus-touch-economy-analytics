from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock, Thread
from typing import Literal

from dofus_touch_economy.cli import load_bigquery_main

BigQuerySyncStatus = Literal["idle", "running", "succeeded", "failed"]
BigQuerySyncRunner = Callable[[tuple[str, ...], Callable[[str], None]], int]
MAX_SYNC_LOG_LINES = 500


@dataclass(frozen=True)
class BigQuerySyncSnapshot:
    status: BigQuerySyncStatus
    started_at: datetime | None
    completed_at: datetime | None
    exit_code: int | None
    lines: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "started_at": None if self.started_at is None else self.started_at.isoformat(),
            "completed_at": (None if self.completed_at is None else self.completed_at.isoformat()),
            "exit_code": self.exit_code,
            "lines": list(self.lines),
        }


class BigQuerySyncManager:
    def __init__(
        self,
        project_id: str,
        location: str,
        datasets: tuple[str, ...],
        database_path: Path,
        *,
        runner: BigQuerySyncRunner | None = None,
    ) -> None:
        self.project_id = project_id
        self.location = location
        self.datasets = datasets
        self.database_path = database_path
        self._runner = runner or self._run_loader
        self._lock = RLock()
        self._status: BigQuerySyncStatus = "idle"
        self._started_at: datetime | None = None
        self._completed_at: datetime | None = None
        self._exit_code: int | None = None
        self._lines: list[str] = []
        self._thread: Thread | None = None

    def snapshot(self) -> BigQuerySyncSnapshot:
        with self._lock:
            return BigQuerySyncSnapshot(
                status=self._status,
                started_at=self._started_at,
                completed_at=self._completed_at,
                exit_code=self._exit_code,
                lines=tuple(self._lines),
            )

    def start(self) -> bool:
        with self._lock:
            if self._status == "running":
                return False
            self._status = "running"
            self._started_at = datetime.now(UTC)
            self._completed_at = None
            self._exit_code = None
            self._lines = []
            self._thread = Thread(target=self._run, name="bigquery-sync", daemon=True)
            thread = self._thread
        thread.start()
        return True

    def wait(self, timeout: float | None = None) -> BigQuerySyncSnapshot:
        with self._lock:
            thread = self._thread
        if thread is not None:
            thread.join(timeout)
        return self.snapshot()

    def _run(self) -> None:
        datasets = ", ".join(self.datasets)
        self._append(
            f"Starting BigQuery snapshot publication: project={self.project_id} "
            f"location={self.location} datasets={datasets}"
        )
        arguments = (
            f"--database-path={self.database_path}",
            f"--project-id={self.project_id}",
            f"--location={self.location}",
            *(f"--dataset={dataset}" for dataset in self.datasets),
        )
        try:
            exit_code = self._runner(arguments, self._append)
        except Exception as error:  # noqa: BLE001 - background boundary records safe failure
            self._append(f"Sync failed unexpectedly: {type(error).__name__}: {error}")
            exit_code = 1

        completed_at = datetime.now(UTC)
        final_status: BigQuerySyncStatus = "succeeded" if exit_code == 0 else "failed"
        self._append(
            "BigQuery snapshot publication completed successfully."
            if exit_code == 0
            else f"BigQuery snapshot publication failed with exit code {exit_code}."
        )
        with self._lock:
            self._status = final_status
            self._completed_at = completed_at
            self._exit_code = exit_code

    def _append(self, message: str) -> None:
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
        lines = message.splitlines() or [""]
        with self._lock:
            self._lines.extend(f"[{timestamp}] {line}" for line in lines)
            if len(self._lines) > MAX_SYNC_LOG_LINES:
                self._lines = self._lines[-MAX_SYNC_LOG_LINES:]

    @staticmethod
    def _run_loader(arguments: tuple[str, ...], emit: Callable[[str], None]) -> int:
        return load_bigquery_main(arguments, emit=emit, emit_error=emit)
