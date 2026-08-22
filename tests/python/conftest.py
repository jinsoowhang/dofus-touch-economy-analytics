import csv
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from dofus_touch_economy.app import create_app
from dofus_touch_economy.config import Settings
from dofus_touch_economy.database import Base, create_engine_for_url, create_session_factory
from dofus_touch_economy.importers.contracts import RECIPE_HEADERS
from dofus_touch_economy.models import Item
from dofus_touch_economy.schemas import PriceObservationCreate
from dofus_touch_economy.services.pricing import PriceService


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


@pytest.fixture
def app(session_factory, tmp_path: Path):
    settings = Settings(
        project_root=tmp_path,
        database_path=tmp_path / "application.sqlite3",
        market_context="Dodge",
        allowed_hosts=("localhost", "127.0.0.1"),
    )
    return create_app(settings=settings, session_factory=session_factory)


@pytest.fixture
def client(app):
    with TestClient(app, base_url="http://localhost") as test_client:
        yield test_client


@pytest.fixture
def catalog_item(session_factory) -> Item:
    with session_factory() as session:
        item = Item(
            display_name="Synthetic Ore",
            normalized_name="synthetic ore",
            category="Ore",
            identity_category="ore",
        )
        session.add(item)
        session.commit()
        return item


@dataclass(frozen=True)
class PricedItem:
    item_uuid: UUID
    previous_uuid: UUID
    current_uuid: UUID


@pytest.fixture
def priced_item(session_factory, catalog_item) -> PricedItem:
    with session_factory() as session:
        service = PriceService(session, "Dodge")
        previous = service.record(
            catalog_item.uuid,
            PriceObservationCreate(
                lot_quantity=1,
                total_price=100,
                observed_at=datetime(2026, 8, 19, tzinfo=UTC),
            ),
        )
        current = service.record(
            catalog_item.uuid,
            PriceObservationCreate(
                lot_quantity=1,
                total_price=120,
                observed_at=datetime(2026, 8, 20, tzinfo=UTC),
            ),
        )
    return PricedItem(catalog_item.uuid, previous.observation_uuid, current.observation_uuid)


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
