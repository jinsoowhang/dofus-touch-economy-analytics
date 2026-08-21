from __future__ import annotations

import argparse
import ipaddress
import json
from collections.abc import Sequence
from pathlib import Path

import uvicorn

from dofus_touch_economy.config import Settings
from dofus_touch_economy.database import create_engine_for_url, create_session_factory
from dofus_touch_economy.importers.service import ImportService


def import_main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import Dofus Touch catalog and recipe exports")
    parser.add_argument("--cost-file", type=Path, default=Path("data/raw/item_cost.csv"))
    parser.add_argument("--recipe-file", type=Path, default=Path("data/raw/item_recipes.csv"))
    parser.add_argument("--report-file", type=Path, default=Path("data/reports/latest-import.json"))
    arguments = parser.parse_args(argv)

    engine = create_engine_for_url(Settings.from_env().database_url)
    try:
        summary = ImportService(create_session_factory(engine)).import_files(
            arguments.cost_file, arguments.recipe_file
        )
    finally:
        engine.dispose()

    arguments.report_file.parent.mkdir(parents=True, exist_ok=True)
    arguments.report_file.write_text(
        json.dumps(summary.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"created_batches={summary.created_batches} accepted={summary.accepted_count} "
        f"rejected={summary.rejected_count} warnings={summary.warning_count} "
        f"report={arguments.report_file}"
    )
    return 1 if summary.rejected_count else 0


def web_main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the local Dofus Touch economy website")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    arguments = parser.parse_args(argv)

    if not _is_loopback(arguments.host):
        parser.error("public binding requires a separate security design")
    if not 1 <= arguments.port <= 65535:
        parser.error("port must be between 1 and 65535")

    uvicorn.run(
        "dofus_touch_economy.app:create_app",
        factory=True,
        host=arguments.host,
        port=arguments.port,
        reload=arguments.reload,
    )
    return 0


def _is_loopback(host: str) -> bool:
    if host.casefold() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


if __name__ == "__main__":
    raise SystemExit(import_main())
