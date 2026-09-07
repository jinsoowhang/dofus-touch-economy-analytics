from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from dofus_touch_economy.catalog_scope import active_catalog_item_clause
from dofus_touch_economy.models import Item, PriceObservation, SaleListing


@dataclass(frozen=True)
class HomeSnapshot:
    active_count: int
    active_value: int
    unpriced_active_count: int
    sold_today: int
    revenue_today: int
    unpriced_sold_today: int
    last_sold_at: datetime | None
    out_of_stock_count: int
    price_review_count: int


class HomeRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def snapshot(
        self, *, as_of: datetime, day_started_at: datetime, review_before: datetime
    ) -> HomeSnapshot:
        active_count, active_value, active_priced = self._session.execute(
            select(
                func.count(),
                func.coalesce(func.sum(SaleListing.asking_price), 0),
                func.count(SaleListing.asking_price),
            ).where(SaleListing.date_sold.is_(None))
        ).one()
        sold_count, revenue, sold_priced = self._session.execute(
            select(
                func.count(),
                func.coalesce(func.sum(SaleListing.asking_price), 0),
                func.count(SaleListing.asking_price),
            ).where(SaleListing.date_sold >= day_started_at, SaleListing.date_sold <= as_of)
        ).one()
        last_sold_at = self._session.scalar(
            select(func.max(SaleListing.date_sold)).where(SaleListing.date_sold <= as_of)
        )
        active_items = select(SaleListing.item_id).where(SaleListing.date_sold.is_(None))
        out_of_stock_count = self._session.scalar(
            select(func.count(func.distinct(SaleListing.item_id))).where(
                SaleListing.date_sold <= as_of,
                SaleListing.item_id.not_in(active_items),
            )
        )
        review_started_at = case(
            (
                PriceObservation.observed_at > SaleListing.selling_started_at,
                PriceObservation.observed_at,
            ),
            else_=SaleListing.selling_started_at,
        )
        price_review_count = self._session.scalar(
            select(func.count())
            .select_from(SaleListing)
            .join(Item, Item.id == SaleListing.item_id)
            .outerjoin(PriceObservation, PriceObservation.id == SaleListing.price_observation_id)
            .where(
                SaleListing.date_sold.is_(None),
                active_catalog_item_clause(Item),
                review_started_at < review_before,
                or_(
                    SaleListing.price_review_snoozed_until.is_(None),
                    SaleListing.price_review_snoozed_until <= as_of,
                ),
            )
        )
        return HomeSnapshot(
            active_count=active_count,
            active_value=active_value,
            unpriced_active_count=active_count - active_priced,
            sold_today=sold_count,
            revenue_today=revenue,
            unpriced_sold_today=sold_count - sold_priced,
            last_sold_at=None if last_sold_at is None else last_sold_at.replace(tzinfo=UTC),
            out_of_stock_count=out_of_stock_count or 0,
            price_review_count=price_review_count or 0,
        )
