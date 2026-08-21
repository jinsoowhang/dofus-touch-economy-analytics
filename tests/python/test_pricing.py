from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from dofus_touch_economy.models import Item, PriceObservation
from dofus_touch_economy.repositories.prices import PriceRepository
from dofus_touch_economy.services.pricing import (
    IngredientPrice,
    ObservationConflict,
    PriceService,
    calculate_recipe_metrics,
    unit_price,
)


def dt(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, tzinfo=UTC)


@pytest.fixture
def item(session) -> Item:
    model = Item(
        display_name="Synthetic Ore", normalized_name="synthetic ore", identity_category="ore"
    )
    session.add(model)
    session.flush()
    return model


def make_observation(
    session,
    item: Item,
    *,
    total_price: int = 100,
    observed_at: datetime | None = None,
    recorded_at: datetime | None = None,
) -> PriceObservation:
    observed_at = observed_at or dt(2026, 8, 20)
    observation = PriceObservation(
        item_id=item.id,
        lot_quantity=1,
        total_price=total_price,
        observed_at=observed_at,
        recorded_at=recorded_at or observed_at + timedelta(seconds=1),
        market_context="Dodge",
    )
    session.add(observation)
    session.flush()
    return observation


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


def test_latest_valid_observation_uses_observed_then_recorded_order(session, item) -> None:
    older_recorded_later = make_observation(
        session,
        item,
        total_price=100,
        observed_at=dt(2026, 8, 19),
        recorded_at=dt(2026, 8, 20),
    )
    newer_observed = make_observation(
        session,
        item,
        total_price=120,
        observed_at=dt(2026, 8, 20),
        recorded_at=dt(2026, 8, 19),
    )
    session.commit()

    assert PriceRepository(session).latest_valid(item.id, "Dodge").id == newer_observed.id
    assert older_recorded_later.id != newer_observed.id


def test_invalidation_restores_previous_valid_price(session, item) -> None:
    previous = make_observation(session, item, total_price=100)
    current = make_observation(session, item, total_price=120)
    session.commit()
    service = PriceService(session, market_context="Dodge")

    service.invalidate(current.uuid, "Mistyped market price")

    assert service.current_for_item(item.id).observation_uuid == previous.uuid


def test_cannot_invalidate_twice(session, item) -> None:
    observation = make_observation(session, item)
    session.commit()
    service = PriceService(session, market_context="Dodge")
    service.invalidate(observation.uuid, "Mistake")

    with pytest.raises(ObservationConflict):
        service.invalidate(observation.uuid, "Again")
