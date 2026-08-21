import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.check_public_files import find_forbidden_tracked_paths


def test_allows_public_repository_files() -> None:
    paths = [
        "README.md",
        ".env.example",
        "data/raw/README.md",
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
        "data/raw/item_sales.csv",
        "private/local_source.xlsx",
        "data/warehouse/dofus_touch.duckdb",
        "dbt_packages/package/dbt_project.yml",
        "logs/dbt.log",
        ".user.yml",
        "target/manifest.json",
    ]

    assert find_forbidden_tracked_paths(paths) == sorted(paths)
