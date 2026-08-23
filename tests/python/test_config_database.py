from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from sqlalchemy import URL, create_engine, text

from dofus_touch_economy.config import Settings
from dofus_touch_economy.database import create_engine_for_url, create_session_factory


def test_settings_defaults_are_deterministic(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("DOFUS_PROJECT_ROOT", str(tmp_path))
    monkeypatch.delenv("DOFUS_APP_DATABASE_PATH", raising=False)
    monkeypatch.delenv("DOFUS_MARKET_CONTEXT", raising=False)
    monkeypatch.delenv("DOFUS_ALLOWED_HOSTS", raising=False)
    monkeypatch.delenv("DOFUS_BIGQUERY_PROJECT_ID", raising=False)
    monkeypatch.delenv("DOFUS_BIGQUERY_LOCATION", raising=False)
    monkeypatch.delenv("DOFUS_BIGQUERY_DATASETS", raising=False)

    settings = Settings.from_env()

    assert settings.project_root == tmp_path.resolve()
    assert settings.database_path == (tmp_path / "data/app/dofus_touch.sqlite3").resolve()
    assert settings.database_url == URL.create(
        "sqlite+pysqlite", database=str(settings.database_path)
    )
    assert settings.market_context == "unspecified"
    assert settings.allowed_hosts == ("127.0.0.1", "localhost")
    assert settings.bigquery_project_id == "claude-projects-489306"
    assert settings.bigquery_location == "US"
    assert settings.bigquery_datasets == ("dofus_dev", "dofus_prod")


def test_database_paths_resolve_relative_to_project_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project_root = tmp_path / "project"
    monkeypatch.setenv("DOFUS_PROJECT_ROOT", str(project_root))
    monkeypatch.setenv("DOFUS_APP_DATABASE_PATH", "custom/app.sqlite3")

    relative_settings = Settings.from_env()

    assert relative_settings.database_path == (project_root / "custom/app.sqlite3").resolve()

    absolute_path = tmp_path / "outside" / "app.sqlite3"
    monkeypatch.setenv("DOFUS_APP_DATABASE_PATH", str(absolute_path))

    absolute_settings = Settings.from_env()

    assert absolute_settings.database_path == absolute_path.resolve()
    assert absolute_settings.database_path.is_absolute()


def test_database_url_preserves_reserved_path_characters(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    database_path = tmp_path / "prices?archived.sqlite3"
    monkeypatch.setenv("DOFUS_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("DOFUS_APP_DATABASE_PATH", str(database_path))

    settings = Settings.from_env()
    engine = create_engine(settings.database_url)

    assert engine.url.database == str(database_path.resolve())
    engine.dispose()


def test_empty_market_context_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOFUS_MARKET_CONTEXT", " \t ")

    with pytest.raises(ValueError, match="^DOFUS_MARKET_CONTEXT must not be empty$"):
        Settings.from_env()


def test_allowed_hosts_are_stripped_and_empty_entries_are_ignored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DOFUS_ALLOWED_HOSTS", " example.test, , 127.0.0.1, ")

    settings = Settings.from_env()

    assert settings.allowed_hosts == ("example.test", "127.0.0.1")


def test_empty_allowed_hosts_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOFUS_ALLOWED_HOSTS", " , \t, ")

    with pytest.raises(ValueError, match="^DOFUS_ALLOWED_HOSTS must contain at least one host$"):
        Settings.from_env()


def test_file_backed_engine_creates_directory_and_sets_sqlite_pragmas(tmp_path: Path) -> None:
    database_path = tmp_path / "nested" / "app.sqlite3"

    engine = create_engine_for_url(f"sqlite+pysqlite:///{database_path}")

    assert database_path.parent.is_dir()
    with engine.connect() as connection:
        foreign_keys = connection.execute(text("PRAGMA foreign_keys")).scalar_one()
        busy_timeout = connection.execute(text("PRAGMA busy_timeout")).scalar_one()
        journal_mode = connection.execute(text("PRAGMA journal_mode")).scalar_one()

    assert foreign_keys == 1
    assert busy_timeout == 5000
    assert str(journal_mode).lower() == "wal"
    engine.dispose()


def test_session_factory_disables_autoflush_and_expiration() -> None:
    engine = create_engine_for_url("sqlite+pysqlite:///:memory:")
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        assert session.autoflush is False
        assert session.expire_on_commit is False

    engine.dispose()


def test_in_memory_database_is_shared_across_threads() -> None:
    engine = create_engine_for_url("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE marker (value INTEGER NOT NULL)"))
        connection.execute(text("INSERT INTO marker VALUES (7)"))

    def read_marker() -> int:
        with engine.connect() as connection:
            return connection.execute(text("SELECT value FROM marker")).scalar_one()

    with ThreadPoolExecutor(max_workers=1) as executor:
        assert executor.submit(read_marker).result() == 7

    engine.dispose()
