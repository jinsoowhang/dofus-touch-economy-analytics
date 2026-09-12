from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, tzinfo
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from dofus_touch_economy.normalization import normalize_item_name
from dofus_touch_economy.schemas import SaleListingResponse
from dofus_touch_economy.services.sales import SalesService


@dataclass(frozen=True)
class DashboardPeriod:
    started_on: date
    ended_on: date
    sold_count: int
    priced_count: int
    revenue: int | None
    cost: Decimal | None
    profit: Decimal | None
    covered_count: int
    coverage: Decimal | None
    margin: Decimal | None
    average_days_to_sell: Decimal | None


@dataclass(frozen=True)
class DashboardItem:
    item_uuid: UUID
    display_name: str
    profit: Decimal
    covered_count: int
    sold_count: int


@dataclass(frozen=True)
class DashboardReport:
    days: int
    current: DashboardPeriod
    previous: DashboardPeriod
    daily: tuple[DashboardPeriod, ...]
    active_count: int
    active_value: int
    price_review_count: int
    last_sold_at: datetime | None
    profit_items: tuple[DashboardItem, ...]
    categories: tuple[str, ...]


class DashboardService:
    def __init__(
        self,
        session: Session,
        market_context: str,
        *,
        display_timezone: tzinfo = UTC,
        as_of: datetime | None = None,
    ) -> None:
        self._sales = SalesService(session, market_context)
        self._display_timezone = display_timezone
        self._as_of = as_of or datetime.now(UTC)

    def report(
        self, days: int = 30, *, categories: tuple[str, ...] = (), item_query: str = ""
    ) -> DashboardReport:
        if not 7 <= days <= 90:
            raise ValueError("dashboard period must be between 7 and 90 days")
        ended_on = self._as_of.astimezone(self._display_timezone).date()
        started_on = ended_on - timedelta(days=days - 1)
        previous_end = started_on - timedelta(days=1)
        previous_start = started_on - timedelta(days=days)
        sold = [
            listing
            for listing in self._sales.sold("sold", "asc")
            if listing.date_sold is not None and listing.date_sold <= self._as_of
        ]
        active = self._sales.active()
        category_choices = tuple(
            sorted({listing.category for listing in [*sold, *active] if listing.category})
        )
        normalized_categories = {normalize_item_name(category) for category in categories}
        normalized_query = normalize_item_name(item_query) if item_query.strip() else ""

        def matches(listing: SaleListingResponse) -> bool:
            return (
                not normalized_categories
                or normalize_item_name(listing.category or "") in normalized_categories
            ) and normalized_query in normalize_item_name(listing.display_name)

        sold = [listing for listing in sold if matches(listing)]
        active = [listing for listing in active if matches(listing)]
        by_date: dict[date, list[SaleListingResponse]] = defaultdict(list)
        for listing in sold:
            if listing.date_sold is not None:
                by_date[listing.date_sold.astimezone(self._display_timezone).date()].append(listing)
        current_listings = [
            listing
            for sold_on, listings in by_date.items()
            if started_on <= sold_on <= ended_on
            for listing in listings
        ]
        previous_listings = [
            listing
            for sold_on, listings in by_date.items()
            if previous_start <= sold_on <= previous_end
            for listing in listings
        ]
        by_item: dict[UUID, list[SaleListingResponse]] = defaultdict(list)
        for listing in current_listings:
            by_item[listing.item_uuid].append(listing)
        profit_items = []
        for item_uuid, listings in by_item.items():
            covered = [listing for listing in listings if listing.profit is not None]
            if covered:
                profit_items.append(
                    DashboardItem(
                        item_uuid=item_uuid,
                        display_name=listings[0].display_name,
                        profit=sum((listing.profit for listing in covered), start=Decimal(0)),
                        covered_count=len(covered),
                        sold_count=len(listings),
                    )
                )
        profit_items.sort(key=lambda item: (-item.profit, item.display_name.casefold()))
        daily = []
        for offset in range(days):
            day = started_on + timedelta(days=offset)
            daily.append(_summarize(by_date.get(day, []), day, day))
        return DashboardReport(
            days=days,
            current=_summarize(current_listings, started_on, ended_on),
            previous=_summarize(previous_listings, previous_start, previous_end),
            daily=tuple(daily),
            active_count=len(active),
            active_value=sum(listing.asking_price or 0 for listing in active),
            price_review_count=len(
                self._sales.active_price_reviews(
                    active, as_of=self._as_of, display_timezone=self._display_timezone
                )
            ),
            last_sold_at=max((listing.date_sold for listing in sold), default=None),
            profit_items=tuple(profit_items[:5]),
            categories=category_choices,
        )


def _summarize(
    listings: list[SaleListingResponse], started_on: date, ended_on: date
) -> DashboardPeriod:
    priced = [listing for listing in listings if listing.asking_price is not None]
    covered = [listing for listing in listings if listing.profit is not None]
    covered_revenue = sum(listing.asking_price for listing in covered)
    profit = (
        sum((listing.profit for listing in covered), start=Decimal(0))
        if covered or not listings
        else None
    )
    return DashboardPeriod(
        started_on=started_on,
        ended_on=ended_on,
        sold_count=len(listings),
        priced_count=len(priced),
        revenue=(
            sum(listing.asking_price for listing in priced) if priced or not listings else None
        ),
        cost=(
            sum((listing.recipe_cost for listing in covered), start=Decimal(0))
            if covered or not listings
            else None
        ),
        profit=profit,
        covered_count=len(covered),
        coverage=None if not listings else Decimal(len(covered)) / len(listings),
        margin=None if not covered_revenue or profit is None else profit / covered_revenue,
        average_days_to_sell=(
            sum(
                (
                    Decimal(str((listing.date_sold - listing.selling_started_at).total_seconds()))
                    / Decimal(86_400)
                    for listing in listings
                ),
                start=Decimal(0),
            )
            / len(listings)
            if listings
            else None
        ),
    )
