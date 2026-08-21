from uuid import UUID

from sqlalchemy import select
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
