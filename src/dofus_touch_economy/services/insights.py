from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta, tzinfo
from decimal import Decimal

from sqlalchemy.orm import Session

from dofus_touch_economy.normalization import format_item_display_name, normalize_item_name
from dofus_touch_economy.schemas import SaleListingResponse
from dofus_touch_economy.services.recipes import ProfitOpportunity, RecipeCatalogService
from dofus_touch_economy.services.sales import BestSellerItem, SalesService


@dataclass(frozen=True)
class InsightPeriod:
    started_on: date
    ended_on: date
    sold_count: int
    revenue: int
    average_days_to_sell: Decimal | None


@dataclass(frozen=True)
class CategoryInsight:
    category: str
    professions: tuple[str, ...]
    sold_count: int
    item_count: int
    revenue: int
    average_days_to_sell: Decimal
    active_listing_count: int


@dataclass(frozen=True)
class InsightsReport:
    first_sale_date: date | None
    latest_sale_date: date | None
    completed_sale_count: int
    priced_sale_count: int
    total_revenue: int
    average_days_to_sell: Decimal | None
    active_listing_count: int
    active_listed_value: int
    price_review_count: int
    out_of_stock_count: int
    cost_covered_sale_count: int
    cost_coverage: Decimal | None
    total_known_profit: Decimal
    known_profit_margin: Decimal | None
    latest_period: InsightPeriod | None
    previous_period: InsightPeriod | None
    sales_count_change: Decimal | None
    revenue_change: Decimal | None
    top_seller: BestSellerItem | None
    top_revenue_item: BestSellerItem | None
    fastest_repeat_seller: BestSellerItem | None
    top_revenue_share: Decimal | None
    top_profit_opportunity: ProfitOpportunity | None
    top_roi_opportunity: ProfitOpportunity | None
    profitable_recipe_count: int
    category_insights: tuple[CategoryInsight, ...]


@dataclass
class _CategoryAccumulator:
    display_name: str
    professions: set[str] = field(default_factory=set)
    sold_count: int = 0
    item_count: int = 0
    revenue: int = 0
    total_days_to_sell: Decimal = Decimal(0)
    active_listing_count: int = 0


class InsightsService:
    def __init__(
        self,
        session: Session,
        market_context: str,
        *,
        display_timezone: tzinfo = UTC,
        as_of: datetime | None = None,
    ) -> None:
        self._session = session
        self._market_context = market_context
        self._display_timezone = display_timezone
        self._as_of = as_of or datetime.now(UTC)

    def report(self) -> InsightsReport:
        sales_service = SalesService(self._session, self._market_context)
        sold = sales_service.sold("sold", "asc")
        active = sales_service.active("started", "desc")
        best_sellers = sales_service.best_sellers()
        opportunities = RecipeCatalogService(
            self._session,
            self._market_context,
        ).profit_opportunities()

        sold_dates = [
            listing.date_sold.astimezone(self._display_timezone).date()
            for listing in sold
            if listing.date_sold is not None
        ]
        first_sale_date = min(sold_dates, default=None)
        latest_sale_date = max(sold_dates, default=None)
        latest_period = None
        previous_period = None
        if latest_sale_date is not None:
            latest_started_on = latest_sale_date - timedelta(days=6)
            previous_ended_on = latest_started_on - timedelta(days=1)
            previous_started_on = previous_ended_on - timedelta(days=6)
            latest_period = self._period(sold, latest_started_on, latest_sale_date)
            previous_period = self._period(sold, previous_started_on, previous_ended_on)

        cost_covered = [listing for listing in sold if listing.profit is not None]
        cost_covered_revenue = sum(listing.asking_price or 0 for listing in cost_covered)
        total_known_profit = sum(
            (listing.profit for listing in cost_covered if listing.profit is not None),
            start=Decimal(0),
        )
        fastest_repeat_seller = min(
            (item for item in best_sellers.items if item.sold_count >= 2),
            key=lambda item: (
                item.average_days_to_sell,
                -item.sold_count,
                item.display_name.casefold(),
            ),
            default=None,
        )
        top_revenue_share = (
            None
            if best_sellers.top_revenue_item is None or not best_sellers.total_revenue
            else Decimal(best_sellers.top_revenue_item.total_revenue)
            / Decimal(best_sellers.total_revenue)
        )
        price_reviews = sales_service.active_price_reviews(
            active,
            as_of=self._as_of,
            display_timezone=self._display_timezone,
        )

        return InsightsReport(
            first_sale_date=first_sale_date,
            latest_sale_date=latest_sale_date,
            completed_sale_count=best_sellers.total_sold_count,
            priced_sale_count=best_sellers.priced_sale_count,
            total_revenue=best_sellers.total_revenue,
            average_days_to_sell=best_sellers.average_days_to_sell,
            active_listing_count=len(active),
            active_listed_value=sum(listing.asking_price or 0 for listing in active),
            price_review_count=len(price_reviews),
            out_of_stock_count=len(sales_service.out_of_stock(self._display_timezone)),
            cost_covered_sale_count=len(cost_covered),
            cost_coverage=(
                None
                if not best_sellers.total_sold_count
                else Decimal(len(cost_covered)) / Decimal(best_sellers.total_sold_count)
            ),
            total_known_profit=total_known_profit,
            known_profit_margin=(
                None
                if not cost_covered_revenue
                else total_known_profit / Decimal(cost_covered_revenue)
            ),
            latest_period=latest_period,
            previous_period=previous_period,
            sales_count_change=(
                None
                if latest_period is None or previous_period is None
                else _percentage_change(
                    latest_period.sold_count,
                    previous_period.sold_count,
                )
            ),
            revenue_change=(
                None
                if latest_period is None or previous_period is None
                else _percentage_change(
                    latest_period.revenue,
                    previous_period.revenue,
                )
            ),
            top_seller=best_sellers.best_seller,
            top_revenue_item=best_sellers.top_revenue_item,
            fastest_repeat_seller=fastest_repeat_seller,
            top_revenue_share=top_revenue_share,
            top_profit_opportunity=opportunities.top_profit_item,
            top_roi_opportunity=opportunities.top_roi_item,
            profitable_recipe_count=opportunities.total_count,
            category_insights=self._category_insights(best_sellers.items, active),
        )

    def _period(
        self,
        listings: list[SaleListingResponse],
        started_on: date,
        ended_on: date,
    ) -> InsightPeriod:
        selected = [
            listing
            for listing in listings
            if listing.date_sold is not None
            and started_on
            <= listing.date_sold.astimezone(self._display_timezone).date()
            <= ended_on
        ]
        total_days = sum(
            (
                Decimal(str((listing.date_sold - listing.selling_started_at).total_seconds()))
                / Decimal(86_400)
                for listing in selected
                if listing.date_sold is not None
            ),
            start=Decimal(0),
        )
        return InsightPeriod(
            started_on=started_on,
            ended_on=ended_on,
            sold_count=len(selected),
            revenue=sum(listing.asking_price or 0 for listing in selected),
            average_days_to_sell=(None if not selected else total_days / Decimal(len(selected))),
        )

    def _category_insights(
        self,
        sold_items: tuple[BestSellerItem, ...],
        active: list[SaleListingResponse],
    ) -> tuple[CategoryInsight, ...]:
        categories: dict[str, _CategoryAccumulator] = {}
        for item in sold_items:
            key, display_name = _category_identity(item.category)
            category = categories.setdefault(key, _CategoryAccumulator(display_name))
            if item.profession is not None:
                category.professions.add(item.profession)
            category.sold_count += item.sold_count
            category.item_count += 1
            category.revenue += item.total_revenue
            category.total_days_to_sell += item.average_days_to_sell * item.sold_count
        active_counts: dict[str, int] = defaultdict(int)
        for listing in active:
            key, _display_name = _category_identity(listing.category)
            active_counts[key] += 1
        for key, category in categories.items():
            category.active_listing_count = active_counts[key]
        return tuple(
            CategoryInsight(
                category=category.display_name,
                professions=tuple(sorted(category.professions, key=str.casefold)),
                sold_count=category.sold_count,
                item_count=category.item_count,
                revenue=category.revenue,
                average_days_to_sell=(category.total_days_to_sell / Decimal(category.sold_count)),
                active_listing_count=category.active_listing_count,
            )
            for category in sorted(
                categories.values(),
                key=lambda category: (
                    -category.revenue,
                    -category.sold_count,
                    category.display_name.casefold(),
                ),
            )
        )


def _percentage_change(current: int, previous: int) -> Decimal | None:
    if previous == 0:
        return None
    return (Decimal(current) - Decimal(previous)) / Decimal(previous)


def _category_identity(category: str | None) -> tuple[str, str]:
    if category is None or not category.strip():
        return "", "Uncategorized"
    normalized_category = normalize_item_name(category)
    if normalized_category in {"cape", "ceremonial cape"}:
        return "cloak", "Cloak"
    return normalized_category, format_item_display_name(category)
