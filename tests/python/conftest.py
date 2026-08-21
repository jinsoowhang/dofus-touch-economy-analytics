import csv
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import pytest

from dofus_touch_economy.database import Base, create_engine_for_url, create_session_factory
from dofus_touch_economy.importers.contracts import RECIPE_HEADERS


@pytest.fixture
def fixture_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def session_factory(tmp_path: Path):
    engine = create_engine_for_url(f"sqlite+pysqlite:///{tmp_path / 'application.sqlite3'}")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    yield factory
    engine.dispose()


@pytest.fixture
def session(session_factory):
    with session_factory() as database_session:
        yield database_session


@dataclass
class SyntheticFiles:
    cost_path: Path
    recipe_path: Path

    @property
    def paths(self) -> tuple[Path, Path]:
        return self.cost_path, self.recipe_path

    def write_cost_rows(self, rows: Sequence[tuple[str, str, str]]) -> None:
        with self.cost_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(("raw_material", "category", "price"))
            writer.writerows(rows)

    def write_recipe(
        self,
        *,
        ingredient: str = "Synthetic Ore",
        quantity: str = "1",
        recipe_item: str = "Synthetic Product",
    ) -> None:
        row = dict.fromkeys(RECIPE_HEADERS, "")
        row.update(
            {
                "recipe_item": recipe_item,
                "profession": "Crafting",
                "raw_material_1": ingredient,
                "quantity_1": quantity,
                "cost_1": "10",
                "total_cost": "10",
                "profit": "5",
                "ROI": "50%",
            }
        )
        with self.recipe_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=RECIPE_HEADERS)
            writer.writeheader()
            writer.writerow(row)


@pytest.fixture
def synthetic_files(tmp_path: Path) -> SyntheticFiles:
    files = SyntheticFiles(tmp_path / "cost.csv", tmp_path / "recipe.csv")
    files.write_cost_rows([("Synthetic Ore", "Ore", "10")])
    files.write_recipe()
    return files
