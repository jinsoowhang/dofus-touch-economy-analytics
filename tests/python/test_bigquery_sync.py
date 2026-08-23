from pathlib import Path
from threading import Event

from dofus_touch_economy.bigquery_sync import BigQuerySyncManager


def test_bigquery_sync_manager_streams_output_and_prevents_overlap(tmp_path: Path) -> None:
    runner_started = Event()
    release_runner = Event()

    def runner(arguments, emit) -> int:
        assert "--project-id=example-project" in arguments
        assert "--dataset=dofus_dev" in arguments
        emit("dataset=dofus_dev table=raw_items status=loading rows=1")
        runner_started.set()
        assert release_runner.wait(timeout=2)
        emit("dataset=dofus_dev status=complete")
        return 0

    manager = BigQuerySyncManager(
        "example-project",
        "US",
        ("dofus_dev",),
        tmp_path / "application.sqlite3",
        runner=runner,
    )

    assert manager.start() is True
    assert runner_started.wait(timeout=2)
    assert manager.start() is False
    running = manager.snapshot()
    assert running.status == "running"
    assert any("raw_items" in line for line in running.lines)

    release_runner.set()
    completed = manager.wait(timeout=2)
    assert completed.status == "succeeded"
    assert completed.exit_code == 0
    assert completed.completed_at is not None
    assert any("completed successfully" in line for line in completed.lines)


def test_bigquery_sync_manager_records_failed_exit(tmp_path: Path) -> None:
    manager = BigQuerySyncManager(
        "example-project",
        "US",
        ("dofus_dev", "dofus_prod"),
        tmp_path / "application.sqlite3",
        runner=lambda _arguments, emit: (emit("authentication failed"), 2)[1],
    )

    assert manager.start() is True
    completed = manager.wait(timeout=2)

    assert completed.status == "failed"
    assert completed.exit_code == 2
    assert any("authentication failed" in line for line in completed.lines)
