from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dofus_touch_economy.config import Settings

DEFAULT_APPROVED_PROFESSIONS = ("Tailor", "Shoemaker", "Jeweller")
DEFAULT_MAXIMUM_IMAGE_BYTES = 20 * 1024 * 1024
DEFAULT_EVIDENCE_RETENTION_DAYS = 90
DEFAULT_CODEX_TIMEOUT_SECONDS = 180


@dataclass(frozen=True)
class CaptureWorkerSettings:
    project_root: Path
    database_path: Path
    market_context: str
    evidence_path: Path
    slack_bot_token: str = field(repr=False)
    slack_app_token: str = field(repr=False)
    slack_workspace_id: str
    slack_channel_id: str
    slack_owner_user_id: str
    codex_binary: str = "codex"
    codex_model: str | None = None
    codex_timeout_seconds: int = DEFAULT_CODEX_TIMEOUT_SECONDS
    approved_professions: tuple[str, ...] = DEFAULT_APPROVED_PROFESSIONS
    maximum_image_bytes: int = DEFAULT_MAXIMUM_IMAGE_BYTES
    evidence_retention_days: int = DEFAULT_EVIDENCE_RETENTION_DAYS
    sold_auto_commit: bool = False
    market_auto_commit: bool = False

    @classmethod
    def from_env(cls) -> CaptureWorkerSettings:
        application = Settings.from_env()
        evidence_path = _resolved_path(
            application.project_root,
            os.environ.get(
                "DOFUS_SLACK_EVIDENCE_PATH",
                "data/app/slack_sales_evidence",
            ),
        )
        professions = tuple(
            value.strip()
            for value in os.environ.get(
                "DOFUS_SLACK_APPROVED_PROFESSIONS",
                ",".join(DEFAULT_APPROVED_PROFESSIONS),
            ).split(",")
            if value.strip()
        )
        if not professions:
            raise ValueError("DOFUS_SLACK_APPROVED_PROFESSIONS must not be empty")
        if len(set(professions)) != len(professions):
            raise ValueError("DOFUS_SLACK_APPROVED_PROFESSIONS must not contain duplicates")

        codex_binary = os.environ.get("DOFUS_SLACK_CODEX_BINARY", "codex").strip()
        if not codex_binary:
            raise ValueError("DOFUS_SLACK_CODEX_BINARY must not be empty")
        codex_model = os.environ.get("DOFUS_SLACK_CODEX_MODEL", "").strip() or None
        codex_timeout_seconds = _positive_integer(
            "DOFUS_SLACK_CODEX_TIMEOUT_SECONDS",
            default=DEFAULT_CODEX_TIMEOUT_SECONDS,
        )

        return cls(
            project_root=application.project_root,
            database_path=application.database_path,
            market_context=application.market_context,
            evidence_path=evidence_path,
            slack_bot_token=_required("DOFUS_SLACK_BOT_TOKEN"),
            slack_app_token=_required("DOFUS_SLACK_APP_TOKEN"),
            slack_workspace_id=_required("DOFUS_SLACK_WORKSPACE_ID"),
            slack_channel_id=_required("DOFUS_SLACK_CHANNEL_ID"),
            slack_owner_user_id=_required("DOFUS_SLACK_OWNER_USER_ID"),
            codex_binary=codex_binary,
            codex_model=codex_model,
            codex_timeout_seconds=codex_timeout_seconds,
            approved_professions=professions,
            sold_auto_commit=_boolean("DOFUS_SLACK_SOLD_AUTO_COMMIT", default=False),
            market_auto_commit=_boolean("DOFUS_SLACK_MARKET_AUTO_COMMIT", default=False),
        )


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} must not be empty")
    return value


def _boolean(name: str, *, default: bool) -> bool:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    value = raw_value.strip().casefold()
    if value == "true":
        return True
    if value == "false":
        return False
    raise ValueError(f"{name} must be true or false")


def _positive_integer(name: str, *, default: int) -> int:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    try:
        value = int(raw_value.strip())
    except ValueError as error:
        raise ValueError(f"{name} must be a positive integer") from error
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _resolved_path(project_root: Path, value: str) -> Path:
    configured_path = Path(value)
    if not configured_path.is_absolute():
        configured_path = project_root / configured_path
    return configured_path.resolve()
