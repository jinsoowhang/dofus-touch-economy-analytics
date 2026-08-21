from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

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


if __name__ == "__main__":
    raise SystemExit(import_main())
