from __future__ import annotations

import argparse
import ipaddress
import json
import os
import sqlite3
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

import uvicorn

from dofus_touch_economy.config import Settings
from dofus_touch_economy.database import create_engine_for_url, create_session_factory
from dofus_touch_economy.importers.service import ImportService

CAPTURE_SCHEMA_VERSION = "0010"


def capture_eval_main(argv: Sequence[str] | None = None) -> int:
    from dofus_touch_economy.capture_evaluation import evaluate_capture_manifest
    from dofus_touch_economy.capture_vision import (
        DEFAULT_CODEX_TIMEOUT_SECONDS,
        CodexCliUnavailableError,
        CodexCliVisionAdapter,
    )

    parser = argparse.ArgumentParser(
        description="Evaluate screenshot extraction against an ignored private gold set"
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument(
        "--codex-binary",
        default=os.environ.get("DOFUS_SLACK_CODEX_BINARY", "codex"),
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("DOFUS_SLACK_CODEX_MODEL", "").strip() or None,
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=int(
            os.environ.get(
                "DOFUS_SLACK_CODEX_TIMEOUT_SECONDS",
                str(DEFAULT_CODEX_TIMEOUT_SECONDS),
            )
        ),
    )
    arguments = parser.parse_args(argv)
    adapter = CodexCliVisionAdapter(
        binary=arguments.codex_binary,
        model=arguments.model,
        timeout_seconds=arguments.timeout_seconds,
    )
    try:
        adapter.check_ready()
    except CodexCliUnavailableError as error:
        print(f"Capture evaluator configuration error: {error}", file=sys.stderr)
        return 2
    summary = evaluate_capture_manifest(
        arguments.manifest,
        adapter,
    )
    return int(summary.passed_count != summary.total_count or summary.false_positive_count != 0)


def load_bigquery_main(
    argv: Sequence[str] | None = None,
    *,
    emit: Callable[[str], None] | None = None,
    emit_error: Callable[[str], None] | None = None,
) -> int:
    from google.api_core.exceptions import GoogleAPIError
    from google.auth.exceptions import GoogleAuthError

    from dofus_touch_economy.analytics_snapshot import extract_operational_snapshot
    from dofus_touch_economy.bigquery_loader import BigQuerySnapshotLoader

    output = emit or print
    error_output = emit_error or (lambda message: print(message, file=sys.stderr))
    parser = argparse.ArgumentParser(
        description="Load an immutable operational SQLite snapshot into BigQuery"
    )
    parser.add_argument("--database-path", type=Path)
    parser.add_argument(
        "--project-id",
        default=os.environ.get("DOFUS_BIGQUERY_PROJECT_ID"),
    )
    parser.add_argument("--dataset", action="append", dest="datasets")
    parser.add_argument(
        "--location",
        default=os.environ.get("DOFUS_BIGQUERY_LOCATION", "US"),
    )
    parser.add_argument("--maximum-bytes-billed", type=int, default=1_000_000_000)
    parser.add_argument("--dry-run", action="store_true")
    arguments = parser.parse_args(argv)
    if not arguments.project_id and not arguments.dry_run:
        parser.error("--project-id or DOFUS_BIGQUERY_PROJECT_ID is required")

    settings = Settings.from_env()
    database_path = arguments.database_path or settings.database_path
    snapshot = extract_operational_snapshot(database_path)
    counts = " ".join(f"{table_name}={count}" for table_name, count in snapshot.row_counts.items())
    output(f"snapshot={snapshot.snapshot_id} schema={snapshot.source_schema_version} {counts}")
    if arguments.dry_run:
        output("dry-run: no BigQuery changes made")
        return 0

    datasets = tuple(arguments.datasets or ("dofus_dev", "dofus_prod"))
    output(
        f"target project={arguments.project_id} location={arguments.location} "
        f"datasets={','.join(datasets)}"
    )
    try:
        loader = BigQuerySnapshotLoader(
            arguments.project_id,
            arguments.location,
            maximum_bytes_billed=arguments.maximum_bytes_billed,
            progress=output,
        )
        results = loader.load(snapshot, datasets)
    except GoogleAuthError:
        error_output(
            "Google Application Default Credentials are unavailable or invalid. "
            "Run 'gcloud auth application-default login' and retry."
        )
        return 2
    except GoogleAPIError as error:
        error_output(f"BigQuery load failed: {error}")
        return 2

    for result in results:
        action = "loaded" if result.loaded else "already-loaded"
        output(
            f"dataset={result.dataset} action={action} "
            f"snapshot={result.snapshot_id} rows={result.row_count}"
        )
    return 0


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


def slack_worker_main(argv: Sequence[str] | None = None) -> int:
    import threading

    from slack_bolt.adapter.socket_mode import SocketModeHandler
    from slack_sdk import WebClient

    from dofus_touch_economy.capture_config import CaptureWorkerSettings
    from dofus_touch_economy.capture_vision import (
        CodexCliUnavailableError,
        CodexCliVisionAdapter,
    )
    from dofus_touch_economy.slack_sales_worker import (
        SlackSalesCaptureWorker,
        build_bolt_app,
        run_processor_loop,
    )

    parser = argparse.ArgumentParser(
        description="Run the private Slack screenshot Sales capture worker"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate worker configuration and database schema without connecting",
    )
    parser.add_argument(
        "--skip-history-catch-up",
        action="store_true",
        help="start live Socket Mode intake without reading missed channel history",
    )
    arguments = parser.parse_args(argv)

    try:
        settings = CaptureWorkerSettings.from_env()
        schema_version = _capture_schema_version(settings.database_path)
    except (FileNotFoundError, sqlite3.Error, ValueError) as error:
        print(f"Slack capture worker configuration error: {error}", file=sys.stderr)
        return 2
    if settings.sold_auto_commit or settings.market_auto_commit:
        print(
            "Slack capture worker is confirmation-only; set both auto-commit flags to false.",
            file=sys.stderr,
        )
        return 2
    if schema_version != CAPTURE_SCHEMA_VERSION:
        print(
            f"Slack capture worker requires database schema {CAPTURE_SCHEMA_VERSION}; "
            f"found {schema_version}. Run the documented Alembic upgrade first.",
            file=sys.stderr,
        )
        return 2
    vision_adapter = CodexCliVisionAdapter(
        binary=settings.codex_binary,
        model=settings.codex_model,
        timeout_seconds=settings.codex_timeout_seconds,
    )
    try:
        vision_adapter.check_ready()
    except CodexCliUnavailableError as error:
        print(f"Slack capture worker configuration error: {error}", file=sys.stderr)
        return 2
    if arguments.check:
        print(
            "Slack capture worker configuration is ready "
            f"schema={schema_version} bridge=codex-cli model={vision_adapter.model_label} "
            "sold_auto_commit=false market_auto_commit=false"
        )
        return 0

    engine = create_engine_for_url(
        Settings.from_env().database_url.set(database=str(settings.database_path))
    )
    session_factory = create_session_factory(engine)
    slack_client = WebClient(token=settings.slack_bot_token)
    worker = SlackSalesCaptureWorker(
        settings,
        session_factory,
        slack_client,
        vision_adapter,
    )
    purged_count = worker.purge_evidence()
    print(f"Slack capture evidence retention purged={purged_count}")
    if not arguments.skip_history_catch_up:
        recovered_count = worker.catch_up()
        print(f"Slack capture history catch-up queued={recovered_count}")

    app = build_bolt_app(settings, worker)
    stop_event = threading.Event()
    processor = threading.Thread(
        target=run_processor_loop,
        kwargs={"worker": worker, "should_stop": stop_event.is_set},
        name="dofus-slack-capture-processor",
        daemon=True,
    )
    processor.start()
    try:
        SocketModeHandler(app, settings.slack_app_token).start()
    finally:
        stop_event.set()
        processor.join(timeout=10)
        engine.dispose()
    return 0


def _capture_schema_version(database_path: Path) -> str:
    resolved_path = database_path.resolve()
    if not resolved_path.is_file():
        raise FileNotFoundError(f"application database does not exist: {resolved_path}")
    with sqlite3.connect(f"file:{resolved_path}?mode=ro", uri=True) as connection:
        row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
    if row is None or not row[0]:
        raise ValueError("application database has no Alembic schema version")
    return str(row[0])


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
        f"created={summary.created_count} names_updated={summary.display_name_updated_count} "
        f"categories_refined={summary.category_refined_count} "
        f"verified={summary.verified_count} excluded={summary.excluded_count} "
        f"catalog={summary.catalog_count} "
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
