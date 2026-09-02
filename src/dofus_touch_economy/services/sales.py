from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, tzinfo
from decimal import Decimal
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from dofus_touch_economy.catalog_scope import active_catalog_item_clause
from dofus_touch_economy.models import Item, PriceObservation, Recipe, SaleListing
from dofus_touch_economy.normalization import normalize_item_name
from dofus_touch_economy.repositories.catalog import CatalogRepository
from dofus_touch_economy.repositories.sales import SalesRepository
from dofus_touch_economy.schemas import (
    SaleItemChoiceResponse,
    SaleListingCreate,
    SaleListingResponse,
    SalePriceUpdate,
)
from dofus_touch_economy.services.pricing import (
    IngredientPrice,
    PriceService,
    calculate_recipe_metrics,
    unit_price,
)

SaleSortField = Literal[
    "name",
    "category",
    "price",
    "cost",
    "profit",
    "started",
    "relisted",
    "sold",
]
SaleSortDirection = Literal["asc", "desc"]
ACTIVE_PRICE_REVIEW_DAYS = 7
ACTIVE_PRICE_MARKDOWN_PERCENT = 5


class SaleItemNotFound(LookupError):
    pass


class SaleListingNotFound(LookupError):
    pass


class SaleListingConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class DailySalesTotal:
    sold_on: date
    total_price: int
    cost_covered_price: int | None
    total_cost: Decimal | None
    total_profit: Decimal | None
    sold_count: int
    priced_count: int
    costed_count: int
    profit_count: int


@dataclass(frozen=True)
class OutOfStockItem:
    item_uuid: UUID
    display_name: str
    category: str | None
    icon_url: str | None
    sold_count: int
    suggested_restock_quantity: int
    last_sold_at: datetime
    last_sale_price: int | None
    current_price: Decimal | None
    recipe_cost: Decimal | None
    last_sale_profit: Decimal | None
    last_sale_roi: Decimal | None
    is_craftable: bool


@dataclass(frozen=True)
class BestSellerItem:
    item_uuid: UUID
    display_name: str
    category: str | None
    profession: str | None
    icon_url: str | None
    sold_count: int
    priced_sale_count: int
    total_revenue: int
    average_sale_price: Decimal | None
    average_days_to_sell: Decimal
    last_sold_at: datetime
    active_listing_count: int
    current_price: Decimal | None
    recipe_cost: Decimal | None
    total_profit: Decimal | None
    estimated_roi: Decimal | None
    is_craftable: bool


@dataclass(frozen=True)
class BestSellerReport:
    items: tuple[BestSellerItem, ...]
    total_sold_count: int
    priced_sale_count: int
    total_revenue: int
    average_days_to_sell: Decimal | None
    best_seller: BestSellerItem | None
    top_revenue_item: BestSellerItem | None
    top_profit_item: BestSellerItem | None


@dataclass(frozen=True)
class SaleListingFilters:
    item_uuid: UUID | None = None
    item_query: str = ""
    category: str = ""
    minimum_price: int | None = None
    maximum_price: int | None = None
    minimum_profit: Decimal | None = None
    maximum_profit: Decimal | None = None
    date_from: date | None = None
    date_to: date | None = None
    display_timezone: tzinfo = UTC


@dataclass(frozen=True)
class ActivePriceReview:
    age_days: int
    suggested_price: int
    suggestion_basis: Literal["completed_sales_median", "standard_markdown"]
    completed_sale_count: int


@dataclass
class _DailySalesAccumulator:
    total_price: int = 0
    cost_covered_price: int = 0
    total_cost: Decimal = Decimal(0)
    total_profit: Decimal = Decimal(0)
    sold_count: int = 0
    priced_count: int = 0
    costed_count: int = 0
    profit_count: int = 0


@dataclass
class _BestSellerAccumulator:
    sold_count: int = 0
    priced_sale_count: int = 0
    total_revenue: int = 0
    profit_count: int = 0
    total_profit: Decimal = Decimal(0)
    total_seconds_to_sell: Decimal = Decimal(0)


class SalesService:
    def __init__(self, session: Session, market_context: str) -> None:
        self._session = session
        self._market_context = market_context
        self._catalog = CatalogRepository(session)
        self._sales = SalesRepository(session)

    def item_choices(self) -> list[SaleItemChoiceResponse]:
        sold_prices: dict[int, list[int]] = defaultdict(list)
        for item_id, asking_price in self._sales.sold_prices():
            sold_prices[item_id].append(asking_price)
        return [
            SaleItemChoiceResponse(
                uuid=item.uuid,
                display_name=item.display_name,
                category=item.category,
                category_key=("" if item.category is None else normalize_item_name(item.category)),
                icon_url=_icon_url(item),
                suggested_price=_median_price(sold_prices[item.id]),
                sold_count=len(sold_prices[item.id]),
            )
            for item in self._catalog.search("", limit=None)
        ]

    def active(
        self,
        sort_field: SaleSortField = "started",
        sort_direction: SaleSortDirection = "desc",
        filters: SaleListingFilters | None = None,
    ) -> list[SaleListingResponse]:
        listings = self._responses(self._sales.active())
        listings = _filter_listings(listings, filters, use_sold_date=False)
        return _sort_listings(listings, sort_field, sort_direction)

    def active_price_reviews(
        self,
        listings: list[SaleListingResponse],
        *,
        as_of: datetime,
        display_timezone: tzinfo,
        review_after_days: int = ACTIVE_PRICE_REVIEW_DAYS,
    ) -> dict[UUID, ActivePriceReview]:
        if not listings:
            return {}
        item_ids_by_uuid = dict(
            self._session.execute(
                select(Item.uuid, Item.id).where(
                    Item.uuid.in_({listing.item_uuid for listing in listings})
                )
            )
            .tuples()
            .all()
        )
        sold_prices: dict[int, list[int]] = defaultdict(list)
        for item_id, asking_price in self._sales.sold_prices():
            sold_prices[item_id].append(asking_price)

        review_date = _as_utc(as_of).astimezone(display_timezone).date()
        reviews: dict[UUID, ActivePriceReview] = {}
        for listing in listings:
            if listing.asking_price is None or listing.asking_price <= 1:
                continue
            review_started_at = listing.relisted_at or listing.selling_started_at
            started_date = review_started_at.astimezone(display_timezone).date()
            age_days = max((review_date - started_date).days, 0)
            if age_days < review_after_days:
                continue

            markdown_price = max(
                1,
                listing.asking_price * (100 - ACTIVE_PRICE_MARKDOWN_PERCENT) // 100,
            )
            markdown_price = min(markdown_price, listing.asking_price - 1)
            item_sold_prices = sold_prices[item_ids_by_uuid[listing.item_uuid]]
            median_price = _median_price(item_sold_prices)
            if median_price is not None and median_price < markdown_price:
                suggested_price = median_price
                suggestion_basis = "completed_sales_median"
            else:
                suggested_price = markdown_price
                suggestion_basis = "standard_markdown"
            reviews[listing.uuid] = ActivePriceReview(
                age_days=age_days,
                suggested_price=suggested_price,
                suggestion_basis=suggestion_basis,
                completed_sale_count=len(item_sold_prices),
            )
        return reviews

    def sold(
        self,
        sort_field: SaleSortField = "sold",
        sort_direction: SaleSortDirection = "desc",
        filters: SaleListingFilters | None = None,
    ) -> list[SaleListingResponse]:
        listings = self._responses(self._sales.sold())
        listings = _filter_listings(listings, filters, use_sold_date=True)
        return _sort_listings(listings, sort_field, sort_direction)

    def out_of_stock(self, display_timezone: tzinfo = UTC) -> list[OutOfStockItem]:
        active_item_ids = {listing.item_id for listing in self._sales.active()}
        sold_listings_by_item: dict[int, list[SaleListing]] = defaultdict(list)
        latest_sold_by_item: dict[int, SaleListing] = {}
        sold_listings = self._sales.sold()
        for listing in sold_listings:
            sold_listings_by_item[listing.item_id].append(listing)
            latest_sold_by_item.setdefault(listing.item_id, listing)

        sales_activity_dates = sorted(
            {
                _as_utc(listing.date_sold).astimezone(display_timezone).date()
                for listing in sold_listings
                if listing.date_sold is not None
            }
        )

        out_of_stock_listings = [
            listing
            for item_id, listing in latest_sold_by_item.items()
            if item_id not in active_item_ids
        ]
        if not out_of_stock_listings:
            return []

        item_ids = [listing.item_id for listing in out_of_stock_listings]
        current_recipe_costs = self._recipe_costs(out_of_stock_listings)
        listing_responses = [
            _response(listing, current_recipe_costs.get(listing.item_id))
            for listing in out_of_stock_listings
        ]
        current_prices = PriceService(self._session, self._market_context).current_for_items(
            item_ids
        )
        craftable_item_ids = set(
            self._session.scalars(
                select(Recipe.crafted_item_id)
                .where(Recipe.crafted_item_id.in_(item_ids))
                .distinct()
            )
        )
        results: list[OutOfStockItem] = []
        for listing, response in zip(out_of_stock_listings, listing_responses, strict=True):
            if response.date_sold is None:  # pragma: no cover - sold query guarantees a date
                continue
            current_price = current_prices.get(listing.item_id)
            last_sale_roi = (
                None
                if response.profit is None
                or response.recipe_cost is None
                or response.recipe_cost == 0
                else response.profit / response.recipe_cost
            )
            results.append(
                OutOfStockItem(
                    item_uuid=response.item_uuid,
                    display_name=response.display_name,
                    category=response.category,
                    icon_url=response.icon_url,
                    sold_count=len(sold_listings_by_item[listing.item_id]),
                    suggested_restock_quantity=_suggested_restock_quantity(
                        sold_listings_by_item[listing.item_id],
                        sales_activity_dates,
                        display_timezone,
                    ),
                    last_sold_at=response.date_sold,
                    last_sale_price=response.asking_price,
                    current_price=(None if current_price is None else current_price.unit_price),
                    recipe_cost=response.recipe_cost,
                    last_sale_profit=response.profit,
                    last_sale_roi=last_sale_roi,
                    is_craftable=listing.item_id in craftable_item_ids,
                )
            )
        return sorted(
            results,
            key=lambda item: (
                item.last_sale_profit is None,
                Decimal(0) if item.last_sale_profit is None else -item.last_sale_profit,
                -item.last_sold_at.timestamp(),
                item.display_name.casefold(),
            ),
        )

    def best_sellers(self) -> BestSellerReport:
        sold_listings = self._sales.sold()
        if not sold_listings:
            return BestSellerReport((), 0, 0, 0, None, None, None, None)

        active_counts: dict[int, int] = defaultdict(int)
        for listing in self._sales.active():
            active_counts[listing.item_id] += 1

        totals: dict[int, _BestSellerAccumulator] = {}
        latest_sold_by_item: dict[int, SaleListing] = {}
        sold_responses = {response.uuid: response for response in self._responses(sold_listings)}
        for listing in sold_listings:
            if listing.date_sold is None:  # pragma: no cover - sold query guarantees a date
                continue
            latest_sold_by_item.setdefault(listing.item_id, listing)
            item_total = totals.setdefault(listing.item_id, _BestSellerAccumulator())
            item_total.sold_count += 1
            item_total.total_seconds_to_sell += Decimal(
                str(
                    (
                        _as_utc(listing.date_sold) - _as_utc(listing.selling_started_at)
                    ).total_seconds()
                )
            )
            if listing.asking_price is not None:
                item_total.priced_sale_count += 1
                item_total.total_revenue += listing.asking_price
            profit = sold_responses[listing.uuid].profit
            if profit is not None:
                item_total.profit_count += 1
                item_total.total_profit += profit

        item_ids = list(latest_sold_by_item)
        current_prices = PriceService(self._session, self._market_context).current_for_items(
            item_ids
        )
        recipe_costs = self._recipe_costs(list(latest_sold_by_item.values()))
        latest_recipes = self._catalog.latest_recipes_for_item_ids(set(item_ids))

        items: list[BestSellerItem] = []
        for item_id, listing in latest_sold_by_item.items():
            if listing.date_sold is None:  # pragma: no cover - sold query guarantees a date
                continue
            item_total = totals[item_id]
            current = current_prices.get(item_id)
            current_price = None if current is None else current.unit_price
            recipe_cost = recipe_costs.get(item_id)
            estimated_profit_per_item = (
                None
                if current_price is None or recipe_cost is None
                else current_price - recipe_cost
            )
            estimated_roi = (
                None
                if estimated_profit_per_item is None or recipe_cost is None or recipe_cost == 0
                else estimated_profit_per_item / recipe_cost
            )
            items.append(
                BestSellerItem(
                    item_uuid=listing.item.uuid,
                    display_name=listing.item.display_name,
                    category=listing.item.category,
                    profession=(
                        None
                        if item_id not in latest_recipes
                        else latest_recipes[item_id].profession
                    ),
                    icon_url=_icon_url(listing.item),
                    sold_count=item_total.sold_count,
                    priced_sale_count=item_total.priced_sale_count,
                    total_revenue=item_total.total_revenue,
                    average_sale_price=(
                        None
                        if not item_total.priced_sale_count
                        else Decimal(item_total.total_revenue)
                        / Decimal(item_total.priced_sale_count)
                    ),
                    average_days_to_sell=(
                        item_total.total_seconds_to_sell
                        / Decimal(86_400)
                        / Decimal(item_total.sold_count)
                    ),
                    last_sold_at=_as_utc(listing.date_sold),
                    active_listing_count=active_counts[item_id],
                    current_price=current_price,
                    recipe_cost=recipe_cost,
                    total_profit=(None if not item_total.profit_count else item_total.total_profit),
                    estimated_roi=estimated_roi,
                    is_craftable=item_id in latest_recipes,
                )
            )

        items.sort(
            key=lambda item: (
                -item.sold_count,
                -item.total_revenue,
                item.display_name.casefold(),
            )
        )
        total_sold_count = sum(item.sold_count for item in items)
        priced_sale_count = sum(item.priced_sale_count for item in items)
        total_revenue = sum(item.total_revenue for item in items)
        total_seconds_to_sell = sum(
            (totals[item_id].total_seconds_to_sell for item_id in latest_sold_by_item),
            start=Decimal(0),
        )
        top_revenue_item = (
            None
            if not priced_sale_count
            else min(
                items,
                key=lambda item: (
                    -item.total_revenue,
                    -item.sold_count,
                    item.display_name.casefold(),
                ),
            )
        )
        profit_items = [item for item in items if item.total_profit is not None]
        top_profit_item = (
            None
            if not profit_items
            else min(
                profit_items,
                key=lambda item: (
                    -item.total_profit,
                    -item.sold_count,
                    item.display_name.casefold(),
                ),
            )
        )
        return BestSellerReport(
            items=tuple(items),
            total_sold_count=total_sold_count,
            priced_sale_count=priced_sale_count,
            total_revenue=total_revenue,
            average_days_to_sell=(
                total_seconds_to_sell / Decimal(86_400) / Decimal(total_sold_count)
            ),
            best_seller=items[0],
            top_revenue_item=top_revenue_item,
            top_profit_item=top_profit_item,
        )

    def daily_totals(
        self,
        display_timezone: tzinfo,
        listings: list[SaleListingResponse] | None = None,
    ) -> list[DailySalesTotal]:
        totals: dict[date, _DailySalesAccumulator] = {}
        for listing in listings if listings is not None else self.sold("sold", "asc"):
            if listing.date_sold is None:  # pragma: no cover - sold query guarantees a date
                continue
            sold_on = listing.date_sold.astimezone(display_timezone).date()
            daily = totals.setdefault(sold_on, _DailySalesAccumulator())
            daily.sold_count += 1
            if listing.asking_price is not None:
                daily.total_price += listing.asking_price
                daily.priced_count += 1
            if listing.profit is not None:
                if listing.asking_price is None or listing.recipe_cost is None:
                    raise ValueError("known sale profit requires both price and recipe cost")
                daily.cost_covered_price += listing.asking_price
                daily.total_cost += listing.recipe_cost
                daily.costed_count += 1
                daily.total_profit += listing.profit
                daily.profit_count += 1
        return [
            DailySalesTotal(
                sold_on=sold_on,
                total_price=values.total_price,
                cost_covered_price=(None if not values.costed_count else values.cost_covered_price),
                total_cost=(None if not values.costed_count else values.total_cost),
                total_profit=(None if not values.profit_count else values.total_profit),
                sold_count=values.sold_count,
                priced_count=values.priced_count,
                costed_count=values.costed_count,
                profit_count=values.profit_count,
            )
            for sold_on, values in sorted(totals.items())
        ]

    def start(self, command: SaleListingCreate) -> SaleListingResponse:
        return self.start_many([command])[0]

    def start_many(self, commands: list[SaleListingCreate]) -> list[SaleListingResponse]:
        listings = self.create_listings_at(
            commands,
            selling_started_at=datetime.now(UTC),
            source="manual",
            capture_uuid=None,
        )
        self._session.commit()
        return self._responses(listings)

    def create_listings_at(
        self,
        commands: list[SaleListingCreate],
        *,
        selling_started_at: datetime,
        source: str,
        capture_uuid: UUID | None,
    ) -> list[SaleListing]:
        if not commands:
            return []
        if not source.strip():
            raise ValueError("sale listing source must not be empty")
        item_uuids = list(dict.fromkeys(command.item_uuid for command in commands))
        item_ids = {
            item_uuid: item_id
            for item_uuid, item_id in self._session.execute(
                select(Item.uuid, Item.id).where(
                    Item.uuid.in_(item_uuids),
                    active_catalog_item_clause(Item),
                )
            )
        }
        missing_item_uuids = [item_uuid for item_uuid in item_uuids if item_uuid not in item_ids]
        if missing_item_uuids:
            raise SaleItemNotFound(str(missing_item_uuids[0]))

        resolved_started_at = _as_utc(selling_started_at)
        listings: list[SaleListing] = []
        for command in commands:
            item_id = item_ids[command.item_uuid]
            observation = self._new_price_observation(
                item_id,
                command.asking_price,
                resolved_started_at,
                source=source,
            )
            listing = SaleListing(
                item_id=item_id,
                price_observation=observation,
                lot_quantity=1,
                asking_price=command.asking_price,
                selling_started_at=resolved_started_at,
                listing_source=source,
                listing_capture_uuid=capture_uuid,
            )
            self._session.add(listing)
            listings.append(listing)
        self._session.flush()
        return listings

    def duplicate(self, listing_uuid: UUID) -> SaleListingResponse:
        original = self._sales.get_by_uuid(listing_uuid)
        if original is None:
            raise SaleListingNotFound(str(listing_uuid))
        duplicate = SaleListing(
            item_id=original.item_id,
            lot_quantity=1,
            asking_price=original.asking_price,
            selling_started_at=datetime.now(UTC),
            listing_source="manual",
        )
        self._session.add(duplicate)
        self._session.commit()
        return self._responses([self._sales.get_by_uuid(duplicate.uuid) or duplicate])[0]

    def delete(self, listing_uuid: UUID) -> SaleListingResponse:
        listing = self._sales.get_by_uuid(listing_uuid)
        if listing is None:
            raise SaleListingNotFound(str(listing_uuid))
        response = self._responses([listing])[0]
        self._session.delete(listing)
        self._session.commit()
        return response

    def update_price(
        self,
        listing_uuid: UUID,
        command: SalePriceUpdate,
    ) -> SaleListingResponse:
        existing = self._sales.get_by_uuid(listing_uuid)
        if existing is None:
            raise SaleListingNotFound(str(listing_uuid))
        observation = self._new_price_observation(
            existing.item_id,
            command.asking_price,
            datetime.now(UTC),
        )
        if not self._sales.update_price(
            listing_uuid,
            command.asking_price,
            observation.id,
        ):
            self._session.rollback()
            raise SaleListingConflict(str(listing_uuid))
        existing.price_observation = observation
        self._session.commit()
        listing = self._sales.get_by_uuid(listing_uuid)
        if listing is None:  # pragma: no cover - protected by successful update
            raise SaleListingNotFound(str(listing_uuid))
        return self._responses([listing])[0]

    def _new_price_observation(
        self,
        item_id: int,
        total_price: int,
        observed_at: datetime,
        *,
        source: str = "manual",
    ) -> PriceObservation:
        observation = PriceObservation(
            item_id=item_id,
            lot_quantity=1,
            total_price=total_price,
            observed_at=observed_at,
            market_context=self._market_context,
            source=source,
        )
        self._session.add(observation)
        self._session.flush()
        return observation

    def mark_sold(self, listing_uuid: UUID) -> SaleListingResponse:
        try:
            listings = self.mark_listings_sold_at(
                [listing_uuid],
                sold_at=datetime.now(UTC),
                source="manual",
                capture_uuid=None,
            )
        except (SaleListingNotFound, SaleListingConflict):
            self._session.rollback()
            raise
        self._session.commit()
        return self._responses(listings)[0]

    def mark_sold_many(self, listing_uuids: list[UUID]) -> list[SaleListingResponse]:
        try:
            listings = self.mark_listings_sold_at(
                listing_uuids,
                sold_at=datetime.now(UTC),
                source="manual",
                capture_uuid=None,
            )
        except (SaleListingNotFound, SaleListingConflict):
            self._session.rollback()
            raise
        self._session.commit()
        return self._responses(listings)

    def mark_listings_sold_at(
        self,
        listing_uuids: list[UUID],
        *,
        sold_at: datetime,
        source: str,
        capture_uuid: UUID | None,
        asking_prices: dict[UUID, int] | None = None,
    ) -> list[SaleListing]:
        if not source.strip():
            raise ValueError("sale source must not be empty")
        listings = self._selected_listings(listing_uuids)
        if any(listing.date_sold is not None for listing in listings):
            raise SaleListingConflict("only active listings can be marked as sold")
        resolved_sold_at = _as_utc(sold_at)
        if any(resolved_sold_at < _as_utc(listing.selling_started_at) for listing in listings):
            raise SaleListingConflict("sale timestamp is before the listing start")
        selected_uuids = {listing.uuid for listing in listings}
        price_corrections = asking_prices or {}
        if unexpected_uuids := set(price_corrections) - selected_uuids:
            raise SaleListingConflict(
                f"price correction refers to an unselected listing: {next(iter(unexpected_uuids))}"
            )
        if any(price <= 0 for price in price_corrections.values()):
            raise ValueError("corrected sale prices must be positive")
        for listing in listings:
            asking_price = price_corrections.get(listing.uuid)
            if asking_price is None or asking_price == listing.asking_price:
                continue
            observation = self._new_price_observation(
                listing.item_id,
                asking_price,
                resolved_sold_at,
                source=source,
            )
            if not self._sales.update_price(
                listing.uuid,
                asking_price,
                observation.id,
            ):
                raise SaleListingConflict("selected listing changed before its price was corrected")
            listing.asking_price = asking_price
            listing.price_observation = observation
        recipe_costs_at_sale = self._recipe_costs_at(
            listings,
            {listing.uuid: resolved_sold_at for listing in listings},
        )
        if self._sales.mark_sold_many(
            recipe_costs_at_sale,
            resolved_sold_at,
            sale_source=source,
            sale_capture_uuid=capture_uuid,
        ) != len(listings):
            raise SaleListingConflict("selected listings changed before they were updated")
        self._session.flush()
        return self._selected_listings(listing_uuids)

    def delete_active_many(self, listing_uuids: list[UUID]) -> list[SaleListingResponse]:
        listings = self._selected_listings(listing_uuids)
        if any(listing.date_sold is not None for listing in listings):
            raise SaleListingConflict("only active listings can be deleted in bulk")
        responses = self._responses(listings)
        for listing in listings:
            self._session.delete(listing)
        self._session.commit()
        return responses

    def reopen(self, listing_uuid: UUID) -> SaleListingResponse:
        if not self._sales.reopen(listing_uuid):
            self._session.rollback()
            existing = self._sales.get_by_uuid(listing_uuid)
            if existing is None:
                raise SaleListingNotFound(str(listing_uuid))
            raise SaleListingConflict(str(listing_uuid))
        self._session.commit()
        listing = self._sales.get_by_uuid(listing_uuid)
        if listing is None:  # pragma: no cover - protected by successful update
            raise SaleListingNotFound(str(listing_uuid))
        return self._responses([listing])[0]

    def _selected_listings(self, listing_uuids: list[UUID]) -> list[SaleListing]:
        unique_uuids = list(dict.fromkeys(listing_uuids))
        listings_by_uuid = {
            listing.uuid: listing for listing in self._sales.get_by_uuids(unique_uuids)
        }
        missing_uuids = [value for value in unique_uuids if value not in listings_by_uuid]
        if missing_uuids:
            raise SaleListingNotFound(str(missing_uuids[0]))
        return [listings_by_uuid[value] for value in unique_uuids]

    def _responses(self, listings: list[SaleListing]) -> list[SaleListingResponse]:
        active_listings = [listing for listing in listings if listing.date_sold is None]
        current_costs = self._recipe_costs(active_listings)
        sold_without_snapshot = [
            listing
            for listing in listings
            if listing.date_sold is not None and listing.recipe_cost_at_sale is None
        ]
        historical_costs = self._recipe_costs_at(
            sold_without_snapshot,
            {
                listing.uuid: _as_utc(listing.date_sold)
                for listing in sold_without_snapshot
                if listing.date_sold is not None
            },
        )
        return [
            _response(
                listing,
                (
                    current_costs.get(listing.item_id)
                    if listing.date_sold is None
                    else (
                        historical_costs.get(listing.uuid)
                        if listing.recipe_cost_at_sale is None
                        else _trim_decimal(listing.recipe_cost_at_sale)
                    )
                ),
            )
            for listing in listings
        ]

    def _recipe_costs(self, listings: list[SaleListing]) -> dict[int, Decimal | None]:
        crafted_item_ids = {listing.item_id for listing in listings}
        if not crafted_item_ids:
            return {}
        recipes = self._session.scalars(
            select(Recipe)
            .where(Recipe.crafted_item_id.in_(crafted_item_ids))
            .options(selectinload(Recipe.ingredients))
            .order_by(Recipe.crafted_item_id, Recipe.id.desc())
        )
        latest_recipes: dict[int, Recipe] = {}
        for recipe in recipes:
            latest_recipes.setdefault(recipe.crafted_item_id, recipe)

        ingredient_item_ids = {
            ingredient.item_id
            for recipe in latest_recipes.values()
            for ingredient in recipe.ingredients
            if ingredient.item_id is not None
        }
        current_prices = PriceService(self._session, self._market_context).current_for_items(
            list(ingredient_item_ids)
        )
        costs: dict[int, Decimal | None] = {}
        for item_id in crafted_item_ids:
            recipe = latest_recipes.get(item_id)
            if recipe is None:
                costs[item_id] = None
                continue
            metrics = calculate_recipe_metrics(
                crafted_item_price=None,
                ingredients=[
                    IngredientPrice(
                        quantity=ingredient.quantity,
                        unit_price=(
                            None
                            if ingredient.item_id is None
                            or ingredient.item_id not in current_prices
                            else current_prices[ingredient.item_id].unit_price
                        ),
                    )
                    for ingredient in recipe.ingredients
                ],
            )
            costs[item_id] = metrics.recipe_cost
        return costs

    def _recipe_costs_at(
        self,
        listings: list[SaleListing],
        as_of_by_listing_uuid: dict[UUID, datetime],
    ) -> dict[UUID, Decimal | None]:
        if not listings:
            return {}
        crafted_item_ids = {listing.item_id for listing in listings}
        recipes_by_item: dict[int, list[Recipe]] = defaultdict(list)
        for recipe in self._session.scalars(
            select(Recipe)
            .where(Recipe.crafted_item_id.in_(crafted_item_ids))
            .options(selectinload(Recipe.ingredients))
            .order_by(Recipe.crafted_item_id, Recipe.created_at, Recipe.id)
        ):
            recipes_by_item[recipe.crafted_item_id].append(recipe)

        selected_recipes: dict[UUID, Recipe | None] = {}
        for listing in listings:
            as_of = _as_utc(as_of_by_listing_uuid[listing.uuid])
            available_recipes = recipes_by_item[listing.item_id]
            selected_recipes[listing.uuid] = next(
                (
                    recipe
                    for recipe in reversed(available_recipes)
                    if _as_utc(recipe.created_at) <= as_of
                ),
                available_recipes[-1] if available_recipes else None,
            )

        ingredient_item_ids = {
            ingredient.item_id
            for recipe in selected_recipes.values()
            if recipe is not None
            for ingredient in recipe.ingredients
            if ingredient.item_id is not None
        }
        price_history_by_item: dict[int, list[PriceObservation]] = defaultdict(list)
        if ingredient_item_ids:
            for observation in self._session.scalars(
                select(PriceObservation)
                .where(
                    PriceObservation.item_id.in_(ingredient_item_ids),
                    PriceObservation.market_context == self._market_context,
                    PriceObservation.invalidated_at.is_(None),
                )
                .order_by(
                    PriceObservation.item_id,
                    PriceObservation.observed_at,
                    PriceObservation.recorded_at,
                    PriceObservation.id,
                )
            ):
                price_history_by_item[observation.item_id].append(observation)

        costs: dict[UUID, Decimal | None] = {}
        for listing in listings:
            recipe = selected_recipes[listing.uuid]
            if recipe is None:
                costs[listing.uuid] = None
                continue
            as_of = _as_utc(as_of_by_listing_uuid[listing.uuid])
            ingredient_prices: list[IngredientPrice] = []
            for ingredient in recipe.ingredients:
                observation = (
                    None
                    if ingredient.item_id is None
                    else next(
                        (
                            candidate
                            for candidate in reversed(price_history_by_item[ingredient.item_id])
                            if _as_utc(candidate.observed_at) <= as_of
                            and _as_utc(candidate.recorded_at) <= as_of
                        ),
                        None,
                    )
                )
                ingredient_prices.append(
                    IngredientPrice(
                        quantity=ingredient.quantity,
                        unit_price=(
                            None
                            if observation is None
                            else unit_price(
                                observation.total_price,
                                observation.lot_quantity,
                            )
                        ),
                    )
                )
            costs[listing.uuid] = calculate_recipe_metrics(
                crafted_item_price=None,
                ingredients=ingredient_prices,
            ).recipe_cost
        return costs


def _trim_decimal(value: Decimal) -> Decimal:
    return value.quantize(Decimal(1)) if value == value.to_integral() else value.normalize()


def _response(listing: SaleListing, recipe_cost: Decimal | None) -> SaleListingResponse:
    profit = (
        None
        if listing.asking_price is None or recipe_cost is None
        else Decimal(listing.asking_price) - recipe_cost
    )
    selling_started_at = _as_utc(listing.selling_started_at)
    observation = listing.price_observation
    observation_time = None if observation is None else _as_utc(observation.observed_at)
    relisted_at = (
        observation_time
        if observation_time is not None and observation_time > selling_started_at
        else None
    )
    return SaleListingResponse(
        uuid=listing.uuid,
        item_uuid=listing.item.uuid,
        display_name=listing.item.display_name,
        category=listing.item.category,
        icon_url=_icon_url(listing.item),
        asking_price=listing.asking_price,
        recipe_cost=recipe_cost,
        profit=profit,
        selling_started_at=selling_started_at,
        relisted_at=relisted_at,
        date_sold=None if listing.date_sold is None else _as_utc(listing.date_sold),
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _suggested_restock_quantity(
    sold_listings: list[SaleListing],
    sales_activity_dates: list[date],
    display_timezone: tzinfo,
) -> int:
    active_days_to_sell = 0
    for listing in sold_listings:
        if listing.date_sold is None:  # pragma: no cover - caller supplies sold listings
            continue
        started_on = _as_utc(listing.selling_started_at).astimezone(display_timezone).date()
        sold_on = _as_utc(listing.date_sold).astimezone(display_timezone).date()
        active_days_to_sell += bisect_right(
            sales_activity_dates,
            sold_on,
        ) - bisect_right(sales_activity_dates, started_on)

    average_active_days = Decimal(active_days_to_sell) / Decimal(len(sold_listings))
    if average_active_days <= 1:
        return 3
    if average_active_days <= 5:
        return 2
    return 1


def _icon_url(item: Item) -> str | None:
    return None if item.icon_source_url is None else f"/item-icons/{item.uuid}.png"


def _median_price(prices: list[int]) -> int | None:
    if not prices:
        return None
    prices = sorted(prices)
    midpoint = len(prices) // 2
    if len(prices) % 2:
        return prices[midpoint]
    return (prices[midpoint - 1] + prices[midpoint]) // 2


def _filter_listings(
    listings: list[SaleListingResponse],
    filters: SaleListingFilters | None,
    *,
    use_sold_date: bool,
) -> list[SaleListingResponse]:
    if filters is None:
        return listings
    normalized_item_query = (
        normalize_item_name(filters.item_query) if filters.item_query.strip() else ""
    )
    normalized_category = normalize_item_name(filters.category) if filters.category.strip() else ""

    def matches(listing: SaleListingResponse) -> bool:
        if filters.item_uuid is not None and listing.item_uuid != filters.item_uuid:
            return False
        if normalized_item_query and normalized_item_query not in normalize_item_name(
            listing.display_name
        ):
            return False
        if (
            normalized_category
            and normalize_item_name(listing.category or "") != normalized_category
        ):
            return False
        if filters.minimum_price is not None and (
            listing.asking_price is None or listing.asking_price < filters.minimum_price
        ):
            return False
        if filters.maximum_price is not None and (
            listing.asking_price is None or listing.asking_price > filters.maximum_price
        ):
            return False
        if filters.minimum_profit is not None and (
            listing.profit is None or listing.profit < filters.minimum_profit
        ):
            return False
        if filters.maximum_profit is not None and (
            listing.profit is None or listing.profit > filters.maximum_profit
        ):
            return False
        activity_time = listing.date_sold if use_sold_date else listing.selling_started_at
        if activity_time is None:
            return False
        activity_date = activity_time.astimezone(filters.display_timezone).date()
        if filters.date_from is not None and activity_date < filters.date_from:
            return False
        return filters.date_to is None or activity_date <= filters.date_to

    return [listing for listing in listings if matches(listing)]


def _sort_listings(
    listings: list[SaleListingResponse],
    sort_field: SaleSortField,
    sort_direction: SaleSortDirection,
) -> list[SaleListingResponse]:
    def value(listing: SaleListingResponse):
        if sort_field == "name":
            return listing.display_name.casefold()
        if sort_field == "category":
            return None if listing.category is None else listing.category.casefold()
        if sort_field == "price":
            return listing.asking_price
        if sort_field == "cost":
            return listing.recipe_cost
        if sort_field == "profit":
            return listing.profit
        if sort_field == "started":
            return listing.selling_started_at
        if sort_field == "relisted":
            return listing.relisted_at
        return listing.date_sold

    with_value = [listing for listing in listings if value(listing) is not None]
    without_value = [listing for listing in listings if value(listing) is None]
    with_value.sort(key=lambda listing: listing.display_name.casefold())
    with_value.sort(key=value, reverse=sort_direction == "desc")
    without_value.sort(key=lambda listing: listing.display_name.casefold())
    return [*with_value, *without_value]
