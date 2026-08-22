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

    settings = Settings.from_env()
    engine = create_engine_for_url(settings.database_url)
    try:
        summary = ImportService(
            create_session_factory(engine),
            settings.market_context,
        ).import_files(arguments.cost_file, arguments.recipe_file)
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
        f"prices={summary.price_count} "
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


def fetch_icons_main(argv: Sequence[str] | None = None) -> int:
    from dofus_touch_economy.icon_fetcher import fetch_item_icons

    parser = argparse.ArgumentParser(description="Cache item icons for the local catalog")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--workers", type=int, default=8)
    arguments = parser.parse_args(argv)
    if arguments.workers < 1:
        parser.error("workers must be positive")

    settings = Settings.from_env()
    engine = create_engine_for_url(settings.database_url)
    try:
        summary = fetch_item_icons(
            create_session_factory(engine),
            settings.project_root / "data" / "app" / "item_icons",
            refresh=arguments.refresh,
            max_workers=arguments.workers,
        )
    finally:
        engine.dispose()

    print(
        f"catalog={summary.catalog_count} cached={summary.cached_count} "
        f"touch={summary.touch_match_count} fallback={summary.fallback_match_count} "
        f"wiki={summary.wiki_match_count} "
        f"ambiguous={summary.ambiguous_match_count} downloaded={summary.downloaded_count} "
        f"missing={len(summary.missing_names)} failed={len(summary.failed_names)}"
    )
    for name in summary.missing_names:
        print(f"missing icon: {name}")
    for name in summary.failed_names:
        print(f"failed download: {name}")
    return 1 if summary.missing_names or summary.failed_names else 0


def sync_catalog_main(argv: Sequence[str] | None = None) -> int:
    from dofus_touch_economy.icon_fetcher import sync_touch_catalog

    parser = argparse.ArgumentParser(
        description="Sync exchangeable items and icons from the Dofus Touch client"
    )
    parser.add_argument("--refresh-icons", action="store_true")
    parser.add_argument("--workers", type=int, default=8)
    arguments = parser.parse_args(argv)
    if arguments.workers < 1:
        parser.error("workers must be positive")

    settings = Settings.from_env()
    engine = create_engine_for_url(settings.database_url)
    try:
        summary = sync_touch_catalog(
            create_session_factory(engine),
            settings.project_root / "data" / "app" / "item_icons",
            refresh_icons=arguments.refresh_icons,
            max_workers=arguments.workers,
        )
    finally:
        engine.dispose()

    print(
        f"source={summary.source_count} matched={summary.matched_count} "
        f"created={summary.created_count} catalog={summary.catalog_count} "
        f"cached={summary.cached_count} downloaded={summary.downloaded_count} "
        f"failed={len(summary.failed_names)}"
    )
    for name in summary.failed_names:
        print(f"failed download: {name}")
    return 1 if summary.failed_names else 0


def sync_recipes_main(argv: Sequence[str] | None = None) -> int:
    from dofus_touch_economy.recipe_sync import sync_touch_recipes

    parser = argparse.ArgumentParser(
        description="Sync recipes from the live Dofus Touch client data"
    )
    parser.parse_args(argv)

    settings = Settings.from_env()
    engine = create_engine_for_url(settings.database_url)
    try:
        summary = sync_touch_recipes(create_session_factory(engine))
    finally:
        engine.dispose()

    print(
        f"source={summary.source_count} recipes={summary.recipe_count} "
        f"ingredients={summary.ingredient_count} created_batch={summary.created_batch} "
        f"checksum={summary.checksum}"
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
