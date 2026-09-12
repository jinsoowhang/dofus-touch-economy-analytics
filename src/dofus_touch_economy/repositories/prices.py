from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from dofus_touch_economy.models import PriceObservation


class PriceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def latest_valid(self, item_id: int, market_context: str) -> PriceObservation | None:
        statement = (
            select(PriceObservation)
            .where(
                PriceObservation.item_id == item_id,
                PriceObservation.market_context == market_context,
                PriceObservation.invalidated_at.is_(None),
            )
            .order_by(
                PriceObservation.observed_at.desc(),
                PriceObservation.recorded_at.desc(),
                PriceObservation.id.desc(),
            )
            .limit(1)
        )
        return self._session.scalar(statement)

    def latest_valid_for_market(
        self, market_context: str, item_ids: set[int] | None = None
    ) -> list[PriceObservation]:
        if item_ids == set():
            return []
        ranked = (
            select(
                PriceObservation.id.label("observation_id"),
                func.row_number()
                .over(
                    partition_by=PriceObservation.item_id,
                    order_by=(
                        PriceObservation.observed_at.desc(),
                        PriceObservation.recorded_at.desc(),
                        PriceObservation.id.desc(),
                    ),
                )
                .label("price_rank"),
            )
            .where(
                PriceObservation.market_context == market_context,
                PriceObservation.invalidated_at.is_(None),
                *([] if item_ids is None else [PriceObservation.item_id.in_(item_ids)]),
            )
            .subquery()
        )
        statement = (
            select(PriceObservation)
            .join(ranked, ranked.c.observation_id == PriceObservation.id)
            .where(ranked.c.price_rank == 1)
        )
        return list(self._session.scalars(statement))

    def latest_two_valid_for_items(
        self,
        item_ids: set[int],
        market_context: str,
    ) -> list[PriceObservation]:
        if not item_ids:
            return []
        ranked = (
            select(
                PriceObservation.id.label("observation_id"),
                PriceObservation.item_id.label("item_id"),
                func.row_number()
                .over(
                    partition_by=PriceObservation.item_id,
                    order_by=(
                        PriceObservation.observed_at.desc(),
                        PriceObservation.recorded_at.desc(),
                        PriceObservation.id.desc(),
                    ),
                )
                .label("price_rank"),
            )
            .where(
                PriceObservation.item_id.in_(item_ids),
                PriceObservation.market_context == market_context,
                PriceObservation.invalidated_at.is_(None),
            )
            .subquery()
        )
        statement = (
            select(PriceObservation)
            .join(ranked, ranked.c.observation_id == PriceObservation.id)
            .where(ranked.c.price_rank <= 2)
            .order_by(ranked.c.item_id, ranked.c.price_rank)
        )
        return list(self._session.scalars(statement))

    def history(self, item_id: int, market_context: str, limit: int = 20) -> list[PriceObservation]:
        statement = (
            select(PriceObservation)
            .where(
                PriceObservation.item_id == item_id,
                PriceObservation.market_context == market_context,
            )
            .order_by(
                PriceObservation.observed_at.desc(),
                PriceObservation.recorded_at.desc(),
                PriceObservation.id.desc(),
            )
            .limit(limit)
        )
        return list(self._session.scalars(statement))

    def get_by_uuid(self, observation_uuid: UUID, market_context: str) -> PriceObservation | None:
        return self._session.scalar(
            select(PriceObservation).where(
                PriceObservation.uuid == observation_uuid,
                PriceObservation.market_context == market_context,
            )
        )

    def invalidate_daily_price_group(
        self,
        observation: PriceObservation,
        *,
        day_start: datetime,
        day_end: datetime,
        invalidated_at: datetime,
        reason: str,
    ) -> int:
        result = self._session.execute(
            update(PriceObservation)
            .where(
                PriceObservation.item_id == observation.item_id,
                PriceObservation.market_context == observation.market_context,
                PriceObservation.total_price == observation.total_price,
                PriceObservation.observed_at >= day_start,
                PriceObservation.observed_at < day_end,
                PriceObservation.invalidated_at.is_(None),
            )
            .values(invalidated_at=invalidated_at, invalidation_reason=reason)
            .execution_options(synchronize_session="fetch")
        )
        return result.rowcount
