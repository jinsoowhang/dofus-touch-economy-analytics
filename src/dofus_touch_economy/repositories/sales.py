from collections.abc import Collection
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session, selectinload

from dofus_touch_economy.models import Item, SaleListing


class SalesRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def active(self) -> list[SaleListing]:
        statement = (
            select(SaleListing)
            .where(SaleListing.date_sold.is_(None))
            .options(
                selectinload(SaleListing.item),
                selectinload(SaleListing.price_observation),
            )
            .order_by(SaleListing.selling_started_at.desc(), SaleListing.id.desc())
        )
        return list(self._session.scalars(statement))

    def active_for_item_ids(self, item_ids: Collection[int]) -> list[SaleListing]:
        if not item_ids:
            return []
        statement = (
            select(SaleListing)
            .where(
                SaleListing.item_id.in_(item_ids),
                SaleListing.date_sold.is_(None),
            )
            .options(
                selectinload(SaleListing.item),
                selectinload(SaleListing.price_observation),
            )
            .order_by(SaleListing.selling_started_at, SaleListing.id)
        )
        return list(self._session.scalars(statement))

    def active_total_price(self) -> int:
        statement = select(func.sum(SaleListing.asking_price)).where(
            SaleListing.date_sold.is_(None)
        )
        return self._session.scalar(statement) or 0

    def active_counts_by_item(self) -> dict[UUID, int]:
        statement = (
            select(Item.uuid, func.count(SaleListing.id))
            .join(SaleListing, SaleListing.item_id == Item.id)
            .where(SaleListing.date_sold.is_(None))
            .group_by(Item.uuid)
        )
        return dict(self._session.execute(statement).tuples().all())

    def sold(self) -> list[SaleListing]:
        statement = (
            select(SaleListing)
            .where(SaleListing.date_sold.is_not(None))
            .options(
                selectinload(SaleListing.item),
                selectinload(SaleListing.price_observation),
            )
            .order_by(SaleListing.date_sold.desc(), SaleListing.id.desc())
        )
        return list(self._session.scalars(statement))

    def listing_activity(self) -> list[tuple[datetime, int | None]]:
        statement = select(
            SaleListing.selling_started_at,
            SaleListing.asking_price,
        ).order_by(SaleListing.selling_started_at, SaleListing.id)
        return list(self._session.execute(statement).tuples())

    def sold_prices(self, item_ids: set[int] | None = None) -> list[tuple[int, int]]:
        if item_ids == set():
            return []
        statement = (
            select(SaleListing.item_id, SaleListing.asking_price)
            .where(
                SaleListing.date_sold.is_not(None),
                SaleListing.asking_price.is_not(None),
            )
            .order_by(SaleListing.item_id, SaleListing.asking_price)
        )
        if item_ids is not None:
            statement = statement.where(SaleListing.item_id.in_(item_ids))
        return [
            (item_id, asking_price)
            for item_id, asking_price in self._session.execute(statement)
            if asking_price is not None
        ]

    def counts_for_item(self, item_id: int) -> tuple[int, int]:
        total_count, sold_count = self._session.execute(
            select(
                func.count(SaleListing.id),
                func.count(SaleListing.date_sold),
            ).where(SaleListing.item_id == item_id)
        ).one()
        return total_count - sold_count, sold_count

    def get_by_uuid(self, listing_uuid: UUID) -> SaleListing | None:
        statement = (
            select(SaleListing)
            .where(SaleListing.uuid == listing_uuid)
            .options(
                selectinload(SaleListing.item),
                selectinload(SaleListing.price_observation),
            )
        )
        return self._session.scalar(statement)

    def get_by_uuids(self, listing_uuids: list[UUID]) -> list[SaleListing]:
        if not listing_uuids:
            return []
        statement = (
            select(SaleListing)
            .where(SaleListing.uuid.in_(listing_uuids))
            .options(
                selectinload(SaleListing.item),
                selectinload(SaleListing.price_observation),
            )
        )
        return list(self._session.scalars(statement))

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
                price_review_snoozed_until=None,
            )
        )
        return result.rowcount == 1

    def snooze_price_review(
        self,
        listing_uuid: UUID,
        *,
        until: datetime,
        as_of: datetime,
        expected_price_observation_id: int | None,
    ) -> bool:
        result = self._session.execute(
            update(SaleListing)
            .where(
                SaleListing.uuid == listing_uuid,
                SaleListing.date_sold.is_(None),
                SaleListing.price_observation_id == expected_price_observation_id,
                or_(
                    SaleListing.price_review_snoozed_until.is_(None),
                    SaleListing.price_review_snoozed_until <= as_of,
                ),
            )
            .values(price_review_snoozed_until=until)
            .execution_options(synchronize_session="fetch")
        )
        return result.rowcount == 1

    def mark_sold(
        self,
        listing_uuid: UUID,
        date_sold: datetime,
        recipe_cost_at_sale: Decimal | None,
    ) -> bool:
        result = self._session.execute(
            update(SaleListing)
            .where(
                SaleListing.uuid == listing_uuid,
                SaleListing.date_sold.is_(None),
            )
            .values(
                date_sold=date_sold,
                recipe_cost_at_sale=recipe_cost_at_sale,
            )
        )
        return result.rowcount == 1

    def mark_sold_many(
        self,
        recipe_costs_at_sale: dict[UUID, Decimal | None],
        date_sold: datetime,
        *,
        sale_source: str,
        sale_capture_uuid: UUID | None,
    ) -> int:
        updated_count = 0
        for listing_uuid, recipe_cost_at_sale in recipe_costs_at_sale.items():
            updated_count += int(
                self._session.execute(
                    update(SaleListing)
                    .where(
                        SaleListing.uuid == listing_uuid,
                        SaleListing.date_sold.is_(None),
                    )
                    .values(
                        date_sold=date_sold,
                        recipe_cost_at_sale=recipe_cost_at_sale,
                        sale_source=sale_source,
                        sale_capture_uuid=sale_capture_uuid,
                    )
                ).rowcount
                or 0
            )
        return updated_count

    def reopen(self, listing_uuid: UUID) -> bool:
        result = self._session.execute(
            update(SaleListing)
            .where(
                SaleListing.uuid == listing_uuid,
                SaleListing.date_sold.is_not(None),
            )
            .values(
                date_sold=None,
                recipe_cost_at_sale=None,
                sale_source=None,
                sale_capture_uuid=None,
            )
        )
        return result.rowcount == 1
