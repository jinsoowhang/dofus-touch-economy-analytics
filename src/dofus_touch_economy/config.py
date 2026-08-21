from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    project_root: Path
    database_path: Path
    market_context: str
    allowed_hosts: tuple[str, ...]

    @property
    def database_url(self) -> str:
        return f"sqlite+pysqlite:///{self.database_path}"

    @classmethod
    def from_env(cls) -> Settings:
        default_root = Path(__file__).resolve().parents[2]
        project_root = Path(os.environ.get("DOFUS_PROJECT_ROOT", default_root)).resolve()

        configured_database_path = Path(
            os.environ.get("DOFUS_APP_DATABASE_PATH", "data/app/dofus_touch.sqlite3")
        )
        if not configured_database_path.is_absolute():
            configured_database_path = project_root / configured_database_path
        database_path = configured_database_path.resolve()

        market_context = os.environ.get("DOFUS_MARKET_CONTEXT", "unspecified").strip()
        if not market_context:
            raise ValueError("DOFUS_MARKET_CONTEXT must not be empty")

        allowed_hosts = tuple(
            host.strip()
            for host in os.environ.get("DOFUS_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
            if host.strip()
        )
        if not allowed_hosts:
            raise ValueError("DOFUS_ALLOWED_HOSTS must contain at least one host")

        return cls(
            project_root=project_root,
            database_path=database_path,
            market_context=market_context,
            allowed_hosts=allowed_hosts,
        )
