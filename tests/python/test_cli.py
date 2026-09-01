import json
from pathlib import Path

import pytest
import uvicorn

from dofus_touch_economy.cli import import_main, slack_worker_main, web_main
from dofus_touch_economy.database import Base, create_engine_for_url


def test_import_cli_writes_report_and_prints_only_counts(
    monkeypatch, tmp_path: Path, fixture_dir: Path, capsys
) -> None:
    database_path = tmp_path / "application.sqlite3"
    engine = create_engine_for_url(f"sqlite+pysqlite:///{database_path}")
    Base.metadata.create_all(engine)
    engine.dispose()
    monkeypatch.setenv("DOFUS_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("DOFUS_APP_DATABASE_PATH", str(database_path))
    report_path = tmp_path / "reports" / "import.json"

    result = import_main(
        [
            "--cost-file",
            str(fixture_dir / "item_cost_valid.csv"),
            "--recipe-file",
            str(fixture_dir / "item_recipes_valid.csv"),
            "--report-file",
            str(report_path),
        ]
    )

    output = capsys.readouterr().out
    assert result == 0
    assert "created_batches=2 accepted=3 rejected=0 warnings=0" in output
    assert "prices=2" in output
    assert f"report={report_path}" in output
    assert "Synthetic" not in output
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["created_batches"] == 2
    assert report["price_count"] == 2


def test_import_cli_returns_one_for_rejected_rows(
    monkeypatch, tmp_path: Path, synthetic_files, capsys
) -> None:
    synthetic_files.write_recipe(quantity="")
    database_path = tmp_path / "application.sqlite3"
    engine = create_engine_for_url(f"sqlite+pysqlite:///{database_path}")
    Base.metadata.create_all(engine)
    engine.dispose()
    monkeypatch.setenv("DOFUS_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("DOFUS_APP_DATABASE_PATH", str(database_path))
    report_path = tmp_path / "report.json"

    result = import_main(
        [
            "--cost-file",
            str(synthetic_files.cost_path),
            "--recipe-file",
            str(synthetic_files.recipe_path),
            "--report-file",
            str(report_path),
        ]
    )

    assert result == 1
    assert "rejected=1" in capsys.readouterr().out
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["rejections"][0]["dataset"] == "item_recipes"
    assert report["rejections"][0]["row_number"] == 2
    assert report["rejections"][0]["messages"]


def test_web_main_binds_loopback(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(uvicorn, "run", lambda *args, **kwargs: calls.append((args, kwargs)))

    assert web_main([]) == 0
    assert calls[0][1]["host"] == "127.0.0.1"
    assert calls[0][1]["factory"] is True


def test_web_main_rejects_public_binding(capsys) -> None:
    with pytest.raises(SystemExit) as error:
        web_main(["--host", "0.0.0.0"])

    assert error.value.code == 2
    assert "public binding requires a separate security design" in capsys.readouterr().err


def test_slack_worker_check_validates_config_and_schema_without_connecting(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    database_path = tmp_path / "application.sqlite3"
    engine = create_engine_for_url(f"sqlite+pysqlite:///{database_path}")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"
        )
        connection.exec_driver_sql("INSERT INTO alembic_version VALUES ('0010')")
    engine.dispose()
    monkeypatch.setenv("DOFUS_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("DOFUS_APP_DATABASE_PATH", str(database_path))
    monkeypatch.setenv("DOFUS_SLACK_BOT_TOKEN", "bot-secret")
    monkeypatch.setenv("DOFUS_SLACK_APP_TOKEN", "app-secret")
    monkeypatch.setenv("DOFUS_SLACK_WORKSPACE_ID", "T123")
    monkeypatch.setenv("DOFUS_SLACK_CHANNEL_ID", "C123")
    monkeypatch.setenv("DOFUS_SLACK_OWNER_USER_ID", "U123")
    monkeypatch.setattr(
        "dofus_touch_economy.capture_vision.CodexCliVisionAdapter.check_ready",
        lambda _self: None,
    )

    assert slack_worker_main(["--check"]) == 0

    output = capsys.readouterr().out
    assert "Slack capture worker configuration is ready" in output
    assert "schema=0010" in output
    assert "bridge=codex-cli" in output
    assert "bot-secret" not in output
    assert "app-secret" not in output


def test_slack_worker_check_rejects_outdated_schema(monkeypatch, tmp_path: Path, capsys) -> None:
    database_path = tmp_path / "application.sqlite3"
    engine = create_engine_for_url(f"sqlite+pysqlite:///{database_path}")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"
        )
        connection.exec_driver_sql("INSERT INTO alembic_version VALUES ('0008')")
    engine.dispose()
    monkeypatch.setenv("DOFUS_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("DOFUS_APP_DATABASE_PATH", str(database_path))
    monkeypatch.setenv("DOFUS_SLACK_BOT_TOKEN", "bot-secret")
    monkeypatch.setenv("DOFUS_SLACK_APP_TOKEN", "app-secret")
    monkeypatch.setenv("DOFUS_SLACK_WORKSPACE_ID", "T123")
    monkeypatch.setenv("DOFUS_SLACK_CHANNEL_ID", "C123")
    monkeypatch.setenv("DOFUS_SLACK_OWNER_USER_ID", "U123")

    assert slack_worker_main(["--check"]) == 2

    assert "requires database schema 0010" in capsys.readouterr().err


def test_slack_worker_check_rejects_experimental_auto_commit(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    database_path = tmp_path / "application.sqlite3"
    engine = create_engine_for_url(f"sqlite+pysqlite:///{database_path}")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"
        )
        connection.exec_driver_sql("INSERT INTO alembic_version VALUES ('0010')")
    engine.dispose()
    monkeypatch.setenv("DOFUS_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("DOFUS_APP_DATABASE_PATH", str(database_path))
    monkeypatch.setenv("DOFUS_SLACK_BOT_TOKEN", "bot-secret")
    monkeypatch.setenv("DOFUS_SLACK_APP_TOKEN", "app-secret")
    monkeypatch.setenv("DOFUS_SLACK_WORKSPACE_ID", "T123")
    monkeypatch.setenv("DOFUS_SLACK_CHANNEL_ID", "C123")
    monkeypatch.setenv("DOFUS_SLACK_OWNER_USER_ID", "U123")
    monkeypatch.setenv("DOFUS_SLACK_SOLD_AUTO_COMMIT", "true")

    assert slack_worker_main(["--check"]) == 2

    assert "confirmation-only" in capsys.readouterr().err
