from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from dofus_touch_economy.importers.service import ImportService
from dofus_touch_economy.models import Item
from dofus_touch_economy.schemas import PriceObservationCreate
from dofus_touch_economy.services.catalog import CatalogService
from dofus_touch_economy.services.pricing import PriceService


def price_command(total_price: int) -> PriceObservationCreate:
    return PriceObservationCreate(
        lot_quantity=1,
        total_price=total_price,
        observed_at=datetime(2026, 8, 20, tzinfo=UTC),
    )


def test_search_normalizes_substrings_and_disambiguates_categories(
    session_factory, synthetic_files
) -> None:
    synthetic_files.write_cost_rows([("Shared Name", "Ore", "1"), ("Shared Name", "Fiber", "2")])
    ImportService(session_factory).import_files(*synthetic_files.paths)

    with session_factory() as session:
        results = CatalogService(session, "Dodge").search("  ARED   NA ")

    assert [(result.display_name, result.category) for result in results] == [
        ("Shared Name", "Fiber"),
        ("Shared Name", "Ore"),
    ]


def test_unresolved_ingredient_makes_metrics_incomplete(session_factory, synthetic_files) -> None:
    synthetic_files.write_cost_rows([("Shared Name", "Ore", "1"), ("Shared Name", "Fiber", "2")])
    synthetic_files.write_recipe(ingredient="Shared Name")
    ImportService(session_factory).import_files(*synthetic_files.paths)

    with session_factory() as session:
        product = session.scalar(select(Item).where(Item.normalized_name == "synthetic product"))
        assert product is not None
        detail = CatalogService(session, "Dodge").detail(product.uuid)

    assert detail.metrics is not None
    assert detail.metrics.is_complete is False
    assert detail.metrics.recipe_cost is None


def test_fully_priced_recipe_returns_exact_decimal_metrics(session_factory, fixture_dir) -> None:
    ImportService(session_factory).import_files(
        fixture_dir / "item_cost_valid.csv", fixture_dir / "item_recipes_valid.csv"
    )
    with session_factory() as session:
        items = {item.normalized_name: item for item in session.scalars(select(Item)).all()}
        price_service = PriceService(session, "Dodge")
        price_service.record(items["synthetic ore"].uuid, price_command(10))
        price_service.record(items["synthetic fiber"].uuid, price_command(20))
        price_service.record(items["synthetic widget"].uuid, price_command(125))

        detail = CatalogService(session, "Dodge").detail(items["synthetic widget"].uuid)

    assert detail.metrics is not None
    assert detail.metrics.recipe_cost == Decimal("80")
    assert detail.metrics.profit == Decimal("45")
    assert detail.metrics.roi == Decimal("0.5625")
    assert detail.metrics.is_complete is True


def test_price_command_requires_timezone() -> None:
    with pytest.raises(ValidationError, match="observed_at must include a timezone"):
        PriceObservationCreate(
            lot_quantity=1,
            total_price=100,
            observed_at=datetime(2026, 8, 20),
        )


def test_detail_uses_latest_recipe_import(session_factory, synthetic_files) -> None:
    service = ImportService(session_factory)
    service.import_files(*synthetic_files.paths)
    synthetic_files.write_recipe(quantity="2")
    service.import_files(*synthetic_files.paths)

    with session_factory() as session:
        product = session.scalar(select(Item).where(Item.normalized_name == "synthetic product"))
        assert product is not None
        detail = CatalogService(session, "Dodge").detail(product.uuid)

    assert detail.recipe is not None
    assert detail.recipe.ingredients[0].quantity == 2
