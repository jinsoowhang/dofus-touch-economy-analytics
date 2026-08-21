from decimal import Decimal

import pytest

from dofus_touch_economy.services.pricing import (
    IngredientPrice,
    calculate_recipe_metrics,
    unit_price,
)


def test_calculates_unit_price_without_float_drift() -> None:
    assert unit_price(total_price=100, lot_quantity=3) == Decimal(100) / Decimal(3)


@pytest.mark.parametrize(("total_price", "lot_quantity"), [(0, 1), (1, 0), (-1, 1)])
def test_unit_price_requires_positive_values(total_price: int, lot_quantity: int) -> None:
    with pytest.raises(ValueError, match="price and quantity must be positive"):
        unit_price(total_price, lot_quantity)


def test_calculates_complete_recipe_metrics() -> None:
    metrics = calculate_recipe_metrics(
        crafted_item_price=Decimal("125"),
        ingredients=[
            IngredientPrice(quantity=2, unit_price=Decimal("10")),
            IngredientPrice(quantity=3, unit_price=Decimal("20")),
        ],
    )

    assert metrics.recipe_cost == Decimal("80")
    assert metrics.profit == Decimal("45")
    assert metrics.roi == Decimal("0.5625")
    assert metrics.is_complete is True


def test_missing_price_never_becomes_zero() -> None:
    metrics = calculate_recipe_metrics(
        crafted_item_price=Decimal("125"),
        ingredients=[IngredientPrice(quantity=2, unit_price=None)],
    )

    assert metrics.recipe_cost is None
    assert metrics.profit is None
    assert metrics.roi is None
    assert metrics.is_complete is False


def test_missing_crafted_item_price_keeps_complete_recipe_cost() -> None:
    metrics = calculate_recipe_metrics(
        crafted_item_price=None,
        ingredients=[IngredientPrice(quantity=2, unit_price=Decimal("10"))],
    )

    assert metrics.recipe_cost == Decimal("20")
    assert metrics.profit is None
    assert metrics.roi is None
    assert metrics.is_complete is True


def test_zero_recipe_cost_has_no_roi() -> None:
    metrics = calculate_recipe_metrics(
        crafted_item_price=Decimal("10"),
        ingredients=[IngredientPrice(quantity=0, unit_price=Decimal("5"))],
    )

    assert metrics.recipe_cost == Decimal("0")
    assert metrics.profit == Decimal("10")
    assert metrics.roi is None
    assert metrics.is_complete is True
