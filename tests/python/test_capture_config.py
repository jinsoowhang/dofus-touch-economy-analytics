from pathlib import Path

import pytest

from dofus_touch_economy.capture_config import CaptureWorkerSettings
from dofus_touch_economy.config import Settings


def test_web_settings_do_not_require_capture_secrets(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DOFUS_PROJECT_ROOT", str(tmp_path))
    monkeypatch.delenv("DOFUS_SLACK_BOT_TOKEN", raising=False)
    monkeypatch.delenv("DOFUS_SLACK_APP_TOKEN", raising=False)

    settings = Settings.from_env()

    assert settings.database_path == tmp_path / "data/app/dofus_touch.sqlite3"


def test_capture_settings_require_worker_secrets(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DOFUS_PROJECT_ROOT", str(tmp_path))
    monkeypatch.delenv("DOFUS_SLACK_BOT_TOKEN", raising=False)
    monkeypatch.delenv("DOFUS_SLACK_APP_TOKEN", raising=False)

    with pytest.raises(ValueError, match="DOFUS_SLACK_BOT_TOKEN"):
        CaptureWorkerSettings.from_env()


def test_capture_settings_load_private_worker_configuration(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("DOFUS_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("DOFUS_SLACK_BOT_TOKEN", "xoxb-private")
    monkeypatch.setenv("DOFUS_SLACK_APP_TOKEN", "xapp-private")
    monkeypatch.setenv("DOFUS_SLACK_WORKSPACE_ID", "T123")
    monkeypatch.setenv("DOFUS_SLACK_CHANNEL_ID", "C123")
    monkeypatch.setenv("DOFUS_SLACK_OWNER_USER_ID", "U123")
    monkeypatch.setenv("DOFUS_SLACK_CODEX_MODEL", "gpt-test")

    settings = CaptureWorkerSettings.from_env()

    assert settings.project_root == tmp_path
    assert settings.database_path == tmp_path / "data/app/dofus_touch.sqlite3"
    assert settings.evidence_path == tmp_path / "data/app/slack_sales_evidence"
    assert settings.slack_workspace_id == "T123"
    assert settings.slack_channel_id == "C123"
    assert settings.slack_owner_user_id == "U123"
    assert settings.codex_binary == "codex"
    assert settings.codex_model == "gpt-test"
    assert settings.codex_timeout_seconds == 180
    assert settings.approved_professions == ("Tailor", "Shoemaker", "Jeweller")
    assert settings.maximum_image_bytes == 20 * 1024 * 1024
    assert settings.evidence_retention_days == 90
    assert settings.sold_auto_commit is False
    assert settings.market_auto_commit is False
    assert "xoxb-private" not in repr(settings)
    assert "xapp-private" not in repr(settings)


@pytest.mark.parametrize(
    "variable",
    ["DOFUS_SLACK_SOLD_AUTO_COMMIT", "DOFUS_SLACK_MARKET_AUTO_COMMIT"],
)
def test_capture_settings_reject_non_boolean_flags(
    monkeypatch,
    tmp_path: Path,
    variable: str,
) -> None:
    monkeypatch.setenv("DOFUS_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("DOFUS_SLACK_BOT_TOKEN", "bot")
    monkeypatch.setenv("DOFUS_SLACK_APP_TOKEN", "app")
    monkeypatch.setenv("DOFUS_SLACK_WORKSPACE_ID", "T123")
    monkeypatch.setenv("DOFUS_SLACK_CHANNEL_ID", "C123")
    monkeypatch.setenv("DOFUS_SLACK_OWNER_USER_ID", "U123")
    monkeypatch.setenv(variable, "sometimes")

    with pytest.raises(ValueError, match=variable):
        CaptureWorkerSettings.from_env()


@pytest.mark.parametrize("value", ["0", "-1", "later"])
def test_capture_settings_reject_invalid_codex_timeout(
    monkeypatch,
    tmp_path: Path,
    value: str,
) -> None:
    monkeypatch.setenv("DOFUS_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("DOFUS_SLACK_BOT_TOKEN", "bot")
    monkeypatch.setenv("DOFUS_SLACK_APP_TOKEN", "app")
    monkeypatch.setenv("DOFUS_SLACK_WORKSPACE_ID", "T123")
    monkeypatch.setenv("DOFUS_SLACK_CHANNEL_ID", "C123")
    monkeypatch.setenv("DOFUS_SLACK_OWNER_USER_ID", "U123")
    monkeypatch.setenv("DOFUS_SLACK_CODEX_TIMEOUT_SECONDS", value)

    with pytest.raises(ValueError, match="DOFUS_SLACK_CODEX_TIMEOUT_SECONDS"):
        CaptureWorkerSettings.from_env()
