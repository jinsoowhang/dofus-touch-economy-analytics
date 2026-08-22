from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from dofus_touch_economy.models import SaleListing


class SalesRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def active(self) -> list[SaleListing]:
        statement = (
            select(SaleListing)
            .where(SaleListing.date_sold.is_(None))
            .options(selectinload(SaleListing.item))
            .order_by(SaleListing.selling_started_at.desc(), SaleListing.id.desc())
        )
        return list(self._session.scalars(statement))

    def sold(self) -> list[SaleListing]:
        statement = (
            select(SaleListing)
            .where(SaleListing.date_sold.is_not(None))
            .options(selectinload(SaleListing.item))
            .order_by(SaleListing.date_sold.desc(), SaleListing.id.desc())
        )
        return list(self._session.scalars(statement))

    def sold_prices(self) -> list[tuple[int, int]]:
        statement = (
            select(SaleListing.item_id, SaleListing.asking_price)
            .where(
                SaleListing.date_sold.is_not(None),
                SaleListing.asking_price.is_not(None),
            )
            .order_by(SaleListing.item_id, SaleListing.asking_price)
        )
        return [
            (item_id, asking_price)
            for item_id, asking_price in self._session.execute(statement)
            if asking_price is not None
        ]

    def get_by_uuid(self, listing_uuid: UUID) -> SaleListing | None:
        statement = (
            select(SaleListing)
            .where(SaleListing.uuid == listing_uuid)
            .options(selectinload(SaleListing.item))
        )
        return self._session.scalar(statement)

    def update_price(
        self,
        listing_uuid: UUID,
        asking_price: int,
        price_observation_id: int,
    ) -> bool:
        result = self._session.execute(
            update(SaleListing)
            .where(
                SaleListing.uuid == listing_uuid,
                SaleListing.date_sold.is_(None),
            )
            .values(
                asking_price=asking_price,
                price_observation_id=price_observation_id,
            )
        )
        return result.rowcount == 1

    def mark_sold(self, listing_uuid: UUID, date_sold: datetime) -> bool:
        result = self._session.execute(
            update(SaleListing)
            .where(
                SaleListing.uuid == listing_uuid,
                SaleListing.date_sold.is_(None),
            )
            .values(date_sold=date_sold)
        )
        return result.rowcount == 1

    def reopen(self, listing_uuid: UUID) -> bool:
        result = self._session.execute(
            update(SaleListing)
            .where(
                SaleListing.uuid == listing_uuid,
                SaleListing.date_sold.is_not(None),
            )
            .values(date_sold=None)
        )
        return result.rowcount == 1
