from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, tzinfo
from decimal import Decimal
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

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
)

SaleSortField = Literal["name", "category", "price", "cost", "profit", "started", "sold"]
SaleSortDirection = Literal["asc", "desc"]


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
    total_cost: Decimal | None
    total_profit: Decimal | None
    sold_count: int
    priced_count: int
    costed_count: int
    profit_count: int


@dataclass
class _DailySalesAccumulator:
    total_price: int = 0
    total_cost: Decimal = Decimal(0)
    total_profit: Decimal = Decimal(0)
    sold_count: int = 0
    priced_count: int = 0
    costed_count: int = 0
    profit_count: int = 0


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
    ) -> list[SaleListingResponse]:
        listings = self._responses(self._sales.active())
        return _sort_listings(listings, sort_field, sort_direction)

    def sold(
        self,
        sort_field: SaleSortField = "sold",
        sort_direction: SaleSortDirection = "desc",
    ) -> list[SaleListingResponse]:
        listings = self._responses(self._sales.sold())
        return _sort_listings(listings, sort_field, sort_direction)

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
            if listing.recipe_cost is not None:
                daily.total_cost += listing.recipe_cost
                daily.costed_count += 1
            if listing.profit is not None:
                daily.total_profit += listing.profit
                daily.profit_count += 1
        return [
            DailySalesTotal(
                sold_on=sold_on,
                total_price=values.total_price,
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
        item_id = self._session.scalar(select(Item.id).where(Item.uuid == command.item_uuid))
        if item_id is None:
            raise SaleItemNotFound(str(command.item_uuid))
        selling_started_at = datetime.now(UTC)
        observation = self._new_price_observation(
            item_id,
            command.asking_price,
            selling_started_at,
        )
        listing = SaleListing(
            item_id=item_id,
            price_observation_id=observation.id,
            lot_quantity=1,
            asking_price=command.asking_price,
            selling_started_at=selling_started_at,
        )
        self._session.add(listing)
        self._session.commit()
        return self._responses([self._sales.get_by_uuid(listing.uuid) or listing])[0]

    def duplicate(self, listing_uuid: UUID) -> SaleListingResponse:
        original = self._sales.get_by_uuid(listing_uuid)
        if original is None:
            raise SaleListingNotFound(str(listing_uuid))
        duplicate = SaleListing(
            item_id=original.item_id,
            lot_quantity=1,
            asking_price=original.asking_price,
            selling_started_at=datetime.now(UTC),
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
    ) -> PriceObservation:
        observation = PriceObservation(
            item_id=item_id,
            lot_quantity=1,
            total_price=total_price,
            observed_at=observed_at,
            market_context=self._market_context,
        )
        self._session.add(observation)
        self._session.flush()
        return observation

    def mark_sold(self, listing_uuid: UUID) -> SaleListingResponse:
        if not self._sales.mark_sold(listing_uuid, datetime.now(UTC)):
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

    def _responses(self, listings: list[SaleListing]) -> list[SaleListingResponse]:
        costs = self._recipe_costs(listings)
        return [_response(listing, costs.get(listing.item_id)) for listing in listings]

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


def _response(listing: SaleListing, recipe_cost: Decimal | None) -> SaleListingResponse:
    profit = (
        None
        if listing.asking_price is None or recipe_cost is None
        else Decimal(listing.asking_price) - recipe_cost
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
        selling_started_at=_as_utc(listing.selling_started_at),
        date_sold=None if listing.date_sold is None else _as_utc(listing.date_sold),
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


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
        return listing.date_sold

    with_value = [listing for listing in listings if value(listing) is not None]
    without_value = [listing for listing in listings if value(listing) is None]
    with_value.sort(key=lambda listing: listing.display_name.casefold())
    with_value.sort(key=value, reverse=sort_direction == "desc")
    without_value.sort(key=lambda listing: listing.display_name.casefold())
    return [*with_value, *without_value]
