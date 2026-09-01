import tomllib
from pathlib import Path


def test_documented_entry_points_exist() -> None:
    scripts = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"][
        "scripts"
    ]

    assert scripts == {
        "dofus-evaluate-captures": "dofus_touch_economy.cli:capture_eval_main",
        "dofus-fetch-icons": "dofus_touch_economy.cli:fetch_icons_main",
        "dofus-import": "dofus_touch_economy.cli:import_main",
        "dofus-load-bigquery": "dofus_touch_economy.cli:load_bigquery_main",
        "dofus-slack-worker": "dofus_touch_economy.cli:slack_worker_main",
        "dofus-sync-catalog": "dofus_touch_economy.cli:sync_catalog_main",
        "dofus-sync-recipes": "dofus_touch_economy.cli:sync_recipes_main",
        "dofus-web": "dofus_touch_economy.cli:web_main",
    }


def test_readme_uses_installed_application_commands() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "uv sync --locked --all-groups" in readme
    assert (
        "DOFUS_APP_DATABASE_PATH=data/app/dofus_touch.sqlite3 uv run alembic upgrade head"
    ) in readme
    assert "uv run dofus-import" in readme
    assert "uv run dofus-load-bigquery --dry-run" in readme
    assert "uv run --env-file .env.slack dofus-slack-worker --check" in readme
    assert "uv run dofus-web" in readme


def test_slack_runbook_keeps_confirmation_and_market_gates_explicit() -> None:
    runbook = Path("docs/slack-screenshot-sales-setup.md").read_text(encoding="utf-8")
    manifest = Path("docs/slack-app-manifest.yml").read_text(encoding="utf-8")

    assert "uv run --env-file .env.slack dofus-slack-worker --check" in runbook
    assert "Never commit `.env.slack`" in runbook
    assert "uv run dofus-evaluate-captures" in runbook
    assert "DOFUS_SLACK_SOLD_AUTO_COMMIT=false" in runbook
    assert "DOFUS_SLACK_MARKET_AUTO_COMMIT=false" in runbook
    assert "marketplace image" in runbook
    assert "message.groups" in manifest
    assert "groups:history" in manifest
    assert "files:read" in manifest
    assert "chat:write" in manifest


def test_ci_does_not_import_private_data() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "dofus-import" not in workflow
    assert "data/raw" not in workflow


def test_full_check_compiles_application_package() -> None:
    check_script = Path("scripts/check.sh").read_text(encoding="utf-8")

    assert "uv run python -m compileall -q src" in check_script


def test_full_check_builds_dbt_against_synthetic_local_sources() -> None:
    check_script = Path("scripts/check.sh").read_text(encoding="utf-8")

    assert "uv run dbt seed --full-refresh --profiles-dir ." in check_script
    assert "uv run dbt build --exclude resource_type:seed --profiles-dir ." in check_script
    assert "uv run sqlfluff lint models analyses tests/dbt" in check_script
