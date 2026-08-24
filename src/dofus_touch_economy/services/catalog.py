from collections.abc import Collection
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from difflib import SequenceMatcher
from typing import Literal
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from dofus_touch_economy.catalog_scope import catalog_exclusion_for_name
from dofus_touch_economy.models import Item
from dofus_touch_economy.normalization import (
    format_item_display_name,
    infer_item_category,
    normalize_item_name,
)
from dofus_touch_economy.repositories.catalog import CatalogRepository
from dofus_touch_economy.repositories.sales import SalesRepository
from dofus_touch_economy.schemas import (
    CurrentPriceResponse,
    ItemCreate,
    ItemDetailResponse,
    ItemSummaryResponse,
    RecipeIngredientResponse,
    RecipeMetricsResponse,
    RecipeResponse,
)
from dofus_touch_economy.services.pricing import (
    IngredientPrice,
    ItemNotFound,
    PriceService,
    calculate_recipe_metrics,
    price_freshness,
)
from dofus_touch_economy.services.recipes import required_profession_level

ItemSortField = Literal["name", "category", "weight", "price", "observed"]
SortDirection = Literal["asc", "desc"]


@dataclass(frozen=True)
class CatalogCategoryChoice:
    key: str
    label: str


class CatalogItemConflict(RuntimeError):
    def __init__(self, candidates: list[ItemSummaryResponse]) -> None:
        super().__init__("catalog item identity already exists")
        self.candidates = candidates


class CatalogItemExcluded(ValueError):
    pass


class CatalogService:
    def __init__(
        self,
        session: Session,
        market_context: str,
        *,
        as_of: datetime | None = None,
    ) -> None:
        self._session = session
        self._catalog = CatalogRepository(session)
        self._sales = SalesRepository(session)
        self._prices = PriceService(session, market_context)
        self._market_context = market_context
        self._as_of = as_of or datetime.now(UTC)

    def search(
        self,
        query: str,
        limit: int | None = 50,
        sort_field: ItemSortField = "name",
        sort_direction: SortDirection = "asc",
        category: str | Collection[str] = "",
    ) -> list[ItemSummaryResponse]:
        repository_limit = limit if sort_field == "name" and sort_direction == "asc" else None
        items = self._catalog.search(query, repository_limit, category)
        current_prices = self._prices.current_for_items([item.id for item in items])
        summaries = [_item_summary(item, current_prices.get(item.id)) for item in items]
        ordered = _sort_item_summaries(summaries, sort_field, sort_direction)
        return ordered if limit is None else ordered[:limit]

    def category_choices(self) -> list[CatalogCategoryChoice]:
        labels: dict[str, str] = {}
        for category in self._catalog.categories():
            key = normalize_item_name(category)
            labels.setdefault(key, format_item_display_name(category))
        return [
            CatalogCategoryChoice(key=key, label=label)
            for key, label in sorted(labels.items(), key=lambda entry: entry[1].casefold())
        ]

    def suggest(
        self,
        query: str,
        limit: int = 5,
        category: str | Collection[str] = "",
    ) -> list[ItemSummaryResponse]:
        if not query.strip():
            return []
        normalized_query = normalize_item_name(query)
        scored = [
            (
                SequenceMatcher(None, normalized_query, item.normalized_name).ratio(),
                item,
            )
            for item in self._catalog.suggestion_candidates(category)
        ]
        close_items = [
            item
            for score, item in sorted(
                scored,
                key=lambda entry: (
                    -entry[0],
                    entry[1].normalized_name,
                    entry[1].identity_category,
                    entry[1].id,
                ),
            )
            if score >= 0.62
        ][:limit]
        return [_item_summary(item) for item in close_items]

    def create_manual(self, command: ItemCreate) -> ItemDetailResponse:
        normalized_name = normalize_item_name(command.display_name)
        exclusion = catalog_exclusion_for_name(normalized_name)
        if exclusion is not None:
            raise CatalogItemExcluded(exclusion.reason)
        category = command.category or infer_item_category(command.display_name)
        identity_category = "" if category is None else normalize_item_name(category)
        existing = self._conflicting_items(
            normalized_name,
            identity_category,
            category_was_supplied=category is not None,
        )
        if existing:
            raise CatalogItemConflict(existing)

        item = Item(
            display_name=command.display_name,
            normalized_name=normalized_name,
            category=category,
            identity_category=identity_category,
            created_source="manual",
        )
        self._session.add(item)
        try:
            self._session.commit()
        except IntegrityError:
            self._session.rollback()
            existing = self._conflicting_items(
                normalized_name,
                identity_category,
                category_was_supplied=category is not None,
            )
            if existing:
                raise CatalogItemConflict(existing) from None
            raise
        return self.detail(item.uuid)

    @staticmethod
    def infer_category(display_name: str) -> str | None:
        return infer_item_category(display_name)

    @staticmethod
    def format_display_name(display_name: str) -> str:
        return format_item_display_name(display_name)

    def _conflicting_items(
        self,
        normalized_name: str,
        identity_category: str,
        *,
        category_was_supplied: bool,
    ) -> list[ItemSummaryResponse]:
        if category_was_supplied:
            exact = self._catalog.find_by_identity(normalized_name, identity_category)
            candidates = [] if exact is None else [exact]
        else:
            candidates = self._catalog.find_by_normalized_name(normalized_name)
        return [_item_summary(item) for item in candidates]

    def detail(self, item_uuid: UUID) -> ItemDetailResponse:
        item = self._catalog.get_by_uuid(item_uuid)
        if item is None:
            raise ItemNotFound(str(item_uuid))

        current_price = self._prices.current_for_item(item.id)
        active_sale_count, sold_sale_count = self._sales.counts_for_item(item.id)
        recipe_response = None
        metrics_response = None
        if item.recipes:
            recipe = max(item.recipes, key=lambda candidate: candidate.id)
            ingredient_responses: list[RecipeIngredientResponse] = []
            ingredient_prices: list[IngredientPrice] = []
            for ingredient in recipe.ingredients:
                ingredient_current = (
                    None
                    if ingredient.item_id is None
                    else self._prices.current_for_item(ingredient.item_id)
                )
                ingredient_unit_price = (
                    None if ingredient_current is None else ingredient_current.unit_price
                )
                ingredient_prices.append(
                    IngredientPrice(
                        quantity=ingredient.quantity,
                        unit_price=ingredient_unit_price,
                    )
                )
                extended_cost = (
                    None
                    if ingredient_unit_price is None
                    else Decimal(ingredient.quantity) * ingredient_unit_price
                )
                price_age_days, price_status = price_freshness(
                    ingredient_current,
                    self._as_of,
                )
                ingredient_responses.append(
                    RecipeIngredientResponse(
                        position=ingredient.position,
                        item_uuid=None if ingredient.item is None else ingredient.item.uuid,
                        display_name=(
                            ingredient.raw_name
                            if ingredient.item is None
                            else ingredient.item.display_name
                        ),
                        icon_url=(None if ingredient.item is None else _icon_url(ingredient.item)),
                        raw_name=ingredient.raw_name,
                        quantity=ingredient.quantity,
                        current_price=ingredient_current,
                        extended_cost=extended_cost,
                        is_resolved=ingredient.item is not None,
                        price_age_days=price_age_days,
                        price_status=price_status,
                    )
                )
            recipe_metrics = calculate_recipe_metrics(
                crafted_item_price=None if current_price is None else current_price.unit_price,
                ingredients=ingredient_prices,
            )
            recipe_response = RecipeResponse(
                uuid=recipe.uuid,
                profession=recipe.profession,
                profession_level=required_profession_level(len(recipe.ingredients)),
                ingredients=ingredient_responses,
            )
            metrics_response = RecipeMetricsResponse(
                recipe_cost=recipe_metrics.recipe_cost,
                profit=recipe_metrics.profit,
                roi=recipe_metrics.roi,
                is_complete=recipe_metrics.is_complete,
            )

        return ItemDetailResponse(
            uuid=item.uuid,
            display_name=item.display_name,
            category=item.category,
            icon_url=_icon_url(item),
            weight=item.weight,
            created_source=item.created_source,
            market_context=self._market_context,
            active_sale_count=active_sale_count,
            sold_sale_count=sold_sale_count,
            current_price=current_price,
            recipe=recipe_response,
            metrics=metrics_response,
            price_history=self._prices.history_for_item(item.id),
        )


def _item_summary(
    item: Item,
    current_price: CurrentPriceResponse | None = None,
) -> ItemSummaryResponse:
    return ItemSummaryResponse(
        uuid=item.uuid,
        display_name=item.display_name,
        category=item.category,
        icon_url=_icon_url(item),
        weight=item.weight,
        created_source=item.created_source,
        current_price=current_price,
    )


def _icon_url(item: Item) -> str | None:
    return None if item.icon_source_url is None else f"/item-icons/{item.uuid}.png"


def _sort_item_summaries(
    items: list[ItemSummaryResponse],
    sort_field: ItemSortField,
    sort_direction: SortDirection,
) -> list[ItemSummaryResponse]:
    def value(item: ItemSummaryResponse):
        if sort_field == "name":
            return item.display_name.casefold()
        if sort_field == "category":
            return None if item.category is None else item.category.casefold()
        if sort_field == "price":
            return None if item.current_price is None else item.current_price.total_price
        if sort_field == "weight":
            return item.weight
        return None if item.current_price is None else item.current_price.observed_at

    with_value = [item for item in items if value(item) is not None]
    without_value = [item for item in items if value(item) is None]
    with_value.sort(key=lambda item: item.display_name.casefold())
    with_value.sort(key=value, reverse=sort_direction == "desc")
    without_value.sort(key=lambda item: item.display_name.casefold())
    return [*with_value, *without_value]
