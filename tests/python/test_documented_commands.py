import tomllib
from pathlib import Path


def test_documented_entry_points_exist() -> None:
    scripts = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"][
        "scripts"
    ]

    assert scripts == {
        "dofus-fetch-icons": "dofus_touch_economy.cli:fetch_icons_main",
        "dofus-import": "dofus_touch_economy.cli:import_main",
        "dofus-sync-catalog": "dofus_touch_economy.cli:sync_catalog_main",
        "dofus-web": "dofus_touch_economy.cli:web_main",
    }


def test_readme_uses_installed_application_commands() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "uv sync --locked --all-groups" in readme
    assert (
        "DOFUS_APP_DATABASE_PATH=data/app/dofus_touch.sqlite3 uv run alembic upgrade head"
    ) in readme
    assert "uv run dofus-import" in readme
    assert "uv run dofus-web" in readme


def test_ci_does_not_import_private_data() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "dofus-import" not in workflow
    assert "data/raw" not in workflow


def test_full_check_compiles_application_package() -> None:
    check_script = Path("scripts/check.sh").read_text(encoding="utf-8")

    assert "uv run python -m compileall -q src" in check_script
