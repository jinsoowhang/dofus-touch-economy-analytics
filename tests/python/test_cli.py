import json
from pathlib import Path

from dofus_touch_economy.cli import import_main
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
    assert f"report={report_path}" in output
    assert "Synthetic" not in output
    assert json.loads(report_path.read_text(encoding="utf-8"))["created_batches"] == 2


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
