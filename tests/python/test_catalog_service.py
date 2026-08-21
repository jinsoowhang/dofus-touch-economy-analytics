from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from dofus_touch_economy.importers.service import ImportService
from dofus_touch_economy.models import Item
from dofus_touch_economy.schemas import ItemCreate, PriceObservationCreate
from dofus_touch_economy.services.catalog import CatalogItemConflict, CatalogService
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


def test_blank_search_lists_full_catalog_alphabetically(session_factory) -> None:
    with session_factory() as session:
        session.add_all(
            [
                Item(display_name="Zeta Item", normalized_name="zeta item", identity_category=""),
                Item(
                    display_name="Alpha Item",
                    normalized_name="alpha item",
                    identity_category="",
                ),
            ]
        )
        session.commit()

    with session_factory() as session:
        results = CatalogService(session, "Dodge").search("", limit=None)

    assert [result.display_name for result in results] == ["Alpha Item", "Zeta Item"]


def test_search_summary_includes_current_price(session_factory, catalog_item) -> None:
    with session_factory() as session:
        PriceService(session, "Dodge").record(catalog_item.uuid, price_command(125))
    with session_factory() as session:
        result = CatalogService(session, "Dodge").search("synthetic ore")[0]

    assert result.current_price is not None
    assert result.current_price.unit_price == Decimal("125")


def test_creates_normalized_manual_catalog_item(session_factory) -> None:
    with session_factory() as session:
        detail = CatalogService(session, "Dodge").create_manual(
            ItemCreate(display_name="  New   Blade  ", category="  Sword  ")
        )

    assert detail.display_name == "New Blade"
    assert detail.category == "Sword"
    assert detail.created_source == "manual"
    with session_factory() as session:
        result = CatalogService(session, "Dodge").search("new blade")
    assert [item.uuid for item in result] == [detail.uuid]


def test_manual_create_title_cases_name_and_infers_category(session_factory) -> None:
    with session_factory() as session:
        detail = CatalogService(session, "Dodge").create_manual(
            ItemCreate(display_name="chouquish belt")
        )

    assert detail.display_name == "Chouquish Belt"
    assert detail.category == "Belt"


def test_manual_category_override_wins_over_inference(session_factory) -> None:
    with session_factory() as session:
        detail = CatalogService(session, "Dodge").create_manual(
            ItemCreate(display_name="decorative belt", category="quest item")
        )

    assert detail.display_name == "Decorative Belt"
    assert detail.category == "Quest Item"


def test_manual_create_rejects_existing_identity(session_factory, catalog_item) -> None:
    with session_factory() as session:
        service = CatalogService(session, "Dodge")
        with pytest.raises(CatalogItemConflict) as error:
            service.create_manual(ItemCreate(display_name=" SYNTHETIC ORE ", category="ore"))

    assert [candidate.uuid for candidate in error.value.candidates] == [catalog_item.uuid]


def test_manual_create_without_category_rejects_any_exact_name_candidate(
    session_factory, synthetic_files
) -> None:
    synthetic_files.write_cost_rows([("Shared Name", "Ore", "1"), ("Shared Name", "Fiber", "2")])
    ImportService(session_factory).import_files(*synthetic_files.paths)

    with session_factory() as session, pytest.raises(CatalogItemConflict) as error:
        CatalogService(session, "Dodge").create_manual(ItemCreate(display_name="Shared Name"))

    assert len(error.value.candidates) == 2


def test_suggestions_find_typo_without_changing_identity(session_factory, catalog_item) -> None:
    with session_factory() as session:
        service = CatalogService(session, "Dodge")
        assert service.search("syntheic ore") == []
        suggestions = service.suggest("syntheic ore")

    assert [suggestion.uuid for suggestion in suggestions] == [catalog_item.uuid]


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
