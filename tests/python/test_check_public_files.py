import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.check_public_files import find_forbidden_tracked_paths


def test_allows_public_repository_files() -> None:
    paths = [
        "README.md",
        ".env.example",
        "data/app/README.md",
        "data/raw/README.md",
        "data/reports/README.md",
        "data/samples/example.csv",
        "data/warehouse/README.md",
        "models/staging/stg_source__items.sql",
    ]

    assert find_forbidden_tracked_paths(paths) == []


def test_rejects_private_or_generated_files() -> None:
    paths = [
        ".env",
        ".env.local",
        "nested/.env",
        "nested/.env.local",
        "nested/.user.yml",
        "uppercase/.ENV",
        "uppercase/.ENV.LOCAL",
        "uppercase/.USER.YML",
        "uppercase/source.XLSX",
        "uppercase/cache.DUCKDB",
        "uppercase/cache.DUCKDB.WAL",
        "data/raw/item_sales.csv",
        ".secrets/dbt-cloud-bigquery.json",
        "private/local_source.xlsx",
        "data/warehouse/dofus_touch.duckdb",
        "dbt_packages/package/dbt_project.yml",
        "logs/dbt.log",
        ".user.yml",
        "target/manifest.json",
    ]

    assert find_forbidden_tracked_paths(paths) == sorted(paths)


def test_rejects_application_state() -> None:
    paths = [
        "data/app/dofus_touch.sqlite3",
        "data/app/dofus_touch.sqlite3-wal",
        "data/app/dofus_touch.sqlite3-shm",
        "data/app/local.db-journal",
        "data/app/local.sqlite-journal",
        "data/app/dofus_touch.sqlite3-journal",
        "data/reports/import-report.json",
        "nested/LOCAL.DB",
        "nested/local.db-journal",
        "nested/local.sqlite-journal",
        "nested/LOCAL.SQLITE3-JOURNAL",
    ]

    assert find_forbidden_tracked_paths(paths) == sorted(paths)
