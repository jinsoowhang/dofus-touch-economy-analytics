from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from dofus_touch_economy.catalog_scope import active_catalog_item_clause
from dofus_touch_economy.models import Item, PriceObservation
from dofus_touch_economy.repositories.prices import PriceRepository
from dofus_touch_economy.schemas import (
    CurrentPriceResponse,
    PriceObservationCreate,
    PriceObservationResponse,
)


class ItemNotFound(LookupError):
    pass


class ObservationNotFound(LookupError):
    pass


class ObservationConflict(RuntimeError):
    pass


PriceStatus = Literal["Missing price", "Stale price", "Current price"]


@dataclass(frozen=True)
class IngredientPrice:
    quantity: int
    unit_price: Decimal | None


@dataclass(frozen=True)
class RecipeMetrics:
    recipe_cost: Decimal | None
    profit: Decimal | None
    roi: Decimal | None
    is_complete: bool


@dataclass(frozen=True)
class PriceComparison:
    current: CurrentPriceResponse
    previous: CurrentPriceResponse | None


def unit_price(total_price: int, lot_quantity: int) -> Decimal:
    if total_price <= 0 or lot_quantity <= 0:
        raise ValueError("price and quantity must be positive")
    return Decimal(total_price) / Decimal(lot_quantity)


def calculate_recipe_metrics(
    crafted_item_price: Decimal | None,
    ingredients: list[IngredientPrice],
) -> RecipeMetrics:
    if any(ingredient.unit_price is None for ingredient in ingredients):
        return RecipeMetrics(recipe_cost=None, profit=None, roi=None, is_complete=False)

    recipe_cost = sum(
        (
            Decimal(ingredient.quantity) * ingredient.unit_price
            for ingredient in ingredients
            if ingredient.unit_price is not None
        ),
        start=Decimal(0),
    )
    profit = None if crafted_item_price is None else crafted_item_price - recipe_cost
    roi = None if profit is None or recipe_cost == 0 else profit / recipe_cost
    return RecipeMetrics(recipe_cost=recipe_cost, profit=profit, roi=roi, is_complete=True)


def price_freshness(
    current_price: CurrentPriceResponse | None,
    as_of: datetime,
) -> tuple[int | None, PriceStatus]:
    if current_price is None:
        return None, "Missing price"
    observed_at = current_price.observed_at.astimezone(UTC)
    reference_time = as_of if as_of.tzinfo is not None else as_of.replace(tzinfo=UTC)
    age_days = max((reference_time.astimezone(UTC).date() - observed_at.date()).days, 0)
    return age_days, "Stale price" if age_days >= 7 else "Current price"


class PriceService:
    def __init__(self, session: Session, market_context: str) -> None:
        self._session = session
        self._market_context = market_context
        self._repository = PriceRepository(session)

    def record(self, item_uuid: UUID, command: PriceObservationCreate) -> PriceObservationResponse:
        item_id = self._session.scalar(
            select(Item.id).where(
                Item.uuid == item_uuid,
                active_catalog_item_clause(Item),
            )
        )
        if item_id is None:
            raise ItemNotFound(str(item_uuid))
        note = command.note.strip() if command.note and command.note.strip() else None
        observation = PriceObservation(
            item_id=item_id,
            lot_quantity=command.lot_quantity,
            total_price=command.total_price,
            observed_at=command.observed_at.astimezone(UTC),
            market_context=self._market_context,
            note=note,
        )
        self._session.add(observation)
        self._session.commit()
        return _observation_response(observation)

    def invalidate(self, observation_uuid: UUID, reason: str) -> PriceObservationResponse:
        stripped_reason = reason.strip()
        if not stripped_reason:
            raise ValueError("invalidation reason must not be blank")
        result = self._session.execute(
            update(PriceObservation)
            .where(
                PriceObservation.uuid == observation_uuid,
                PriceObservation.market_context == self._market_context,
                PriceObservation.invalidated_at.is_(None),
            )
            .values(
                invalidated_at=datetime.now(UTC),
                invalidation_reason=stripped_reason,
            )
        )
        if result.rowcount != 1:
            self._session.rollback()
            existing = self._repository.get_by_uuid(observation_uuid, self._market_context)
            if existing is None:
                raise ObservationNotFound(str(observation_uuid))
            raise ObservationConflict(str(observation_uuid))
        self._session.commit()
        observation = self._repository.get_by_uuid(observation_uuid, self._market_context)
        if observation is None:  # pragma: no cover - protected by the successful update
            raise ObservationNotFound(str(observation_uuid))
        return _observation_response(observation)

    def current_for_item(self, item_id: int) -> CurrentPriceResponse | None:
        observation = self._repository.latest_valid(item_id, self._market_context)
        return None if observation is None else _current_price_response(observation)

    def current_for_items(self, item_ids: list[int]) -> dict[int, CurrentPriceResponse]:
        if not item_ids:
            return {}
        requested_ids = set(item_ids)
        return {
            observation.item_id: _current_price_response(observation)
            for observation in self._repository.latest_valid_for_market(self._market_context)
            if observation.item_id in requested_ids
        }

    def current_and_previous_for_items(
        self,
        item_ids: set[int],
    ) -> dict[int, PriceComparison]:
        observations_by_item: dict[int, list[CurrentPriceResponse]] = {}
        for observation in self._repository.latest_two_valid_for_items(
            item_ids,
            self._market_context,
        ):
            observations_by_item.setdefault(observation.item_id, []).append(
                _current_price_response(observation)
            )
        return {
            item_id: PriceComparison(
                current=observations[0],
                previous=observations[1] if len(observations) == 2 else None,
            )
            for item_id, observations in observations_by_item.items()
        }

    def history_for_item(self, item_id: int, limit: int = 20) -> list[PriceObservationResponse]:
        return [
            _observation_response(observation)
            for observation in self._repository.history(item_id, self._market_context, limit)
        ]

    def item_uuid_for_observation(self, observation_uuid: UUID) -> UUID:
        observation = self._repository.get_by_uuid(observation_uuid, self._market_context)
        if observation is None:
            raise ObservationNotFound(str(observation_uuid))
        return observation.item.uuid


def _current_price_response(observation: PriceObservation) -> CurrentPriceResponse:
    return CurrentPriceResponse(
        observation_uuid=observation.uuid,
        lot_quantity=observation.lot_quantity,
        total_price=observation.total_price,
        unit_price=unit_price(observation.total_price, observation.lot_quantity),
        observed_at=_as_utc(observation.observed_at),
        recorded_at=_as_utc(observation.recorded_at),
        market_context=observation.market_context,
    )


def _observation_response(observation: PriceObservation) -> PriceObservationResponse:
    return PriceObservationResponse(
        **_current_price_response(observation).model_dump(),
        item_uuid=observation.item.uuid,
        note=observation.note,
        source=observation.source,
        invalidated_at=(
            None if observation.invalidated_at is None else _as_utc(observation.invalidated_at)
        ),
        invalidation_reason=observation.invalidation_reason,
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
