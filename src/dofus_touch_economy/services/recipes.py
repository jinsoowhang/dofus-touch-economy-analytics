from dataclasses import dataclass
from decimal import Decimal
from typing import Literal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from dofus_touch_economy.models import Recipe, RecipeIngredient
from dofus_touch_economy.normalization import format_item_display_name, normalize_item_name
from dofus_touch_economy.services.pricing import (
    IngredientPrice,
    PriceService,
    calculate_recipe_metrics,
)

RecipeSortField = Literal[
    "name",
    "category",
    "profession",
    "level",
    "price",
    "cost",
    "profit",
    "roi",
]
RecipeSortDirection = Literal["asc", "desc"]
RecipeEconomicsFilter = Literal["all", "profitable", "non_profitable", "unknown"]
_PROFESSION_LEVEL_BY_INGREDIENT_COUNT = (None, 1, 1, 10, 20, 40, 60, 80, 100)


def required_profession_level(ingredient_count: int) -> int | None:
    if not 1 <= ingredient_count <= 8:
        return None
    return _PROFESSION_LEVEL_BY_INGREDIENT_COUNT[ingredient_count]


@dataclass(frozen=True)
class RecipeCatalogFilters:
    item_query: str = ""
    category: str = ""
    profession: str = ""
    minimum_level: int | None = None
    maximum_level: int | None = None
    economics: RecipeEconomicsFilter = "all"


@dataclass(frozen=True)
class RecipeCatalogRow:
    recipe_uuid: UUID
    item_uuid: UUID
    display_name: str
    category: str | None
    icon_url: str | None
    profession: str
    profession_level: int | None
    current_price: Decimal | None
    recipe_cost: Decimal | None
    profit: Decimal | None
    roi: Decimal | None
    is_complete: bool


@dataclass(frozen=True)
class RecipeCategoryChoice:
    key: str
    label: str


@dataclass(frozen=True)
class RecipeCatalogResult:
    rows: list[RecipeCatalogRow]
    total_count: int
    professions: list[str]
    categories: list[RecipeCategoryChoice]
    minimum_available_level: int
    maximum_available_level: int


class RecipeCatalogService:
    def __init__(self, session: Session, market_context: str) -> None:
        self._session = session
        self._prices = PriceService(session, market_context)

    def browse(
        self,
        filters: RecipeCatalogFilters | None = None,
        sort_field: RecipeSortField = "name",
        sort_direction: RecipeSortDirection = "asc",
    ) -> RecipeCatalogResult:
        rows = self._rows()
        levels = [row.profession_level for row in rows if row.profession_level is not None]
        category_labels: dict[str, str] = {}
        for row in rows:
            if row.category:
                key = normalize_item_name(row.category)
                category_labels.setdefault(key, format_item_display_name(row.category))
        filtered_rows = _filter_rows(rows, filters or RecipeCatalogFilters())
        return RecipeCatalogResult(
            rows=_sort_rows(filtered_rows, sort_field, sort_direction),
            total_count=len(rows),
            professions=sorted({row.profession for row in rows}, key=str.casefold),
            categories=[
                RecipeCategoryChoice(key=key, label=label)
                for key, label in sorted(
                    category_labels.items(),
                    key=lambda entry: entry[1].casefold(),
                )
            ],
            minimum_available_level=min(levels, default=1),
            maximum_available_level=max(levels, default=300),
        )

    def _rows(self) -> list[RecipeCatalogRow]:
        latest_recipe_ids = (
            select(func.max(Recipe.id).label("recipe_id"))
            .group_by(Recipe.crafted_item_id)
            .scalar_subquery()
        )
        recipes = list(
            self._session.scalars(
                select(Recipe)
                .where(Recipe.id.in_(latest_recipe_ids))
                .options(
                    selectinload(Recipe.crafted_item),
                    selectinload(Recipe.ingredients).selectinload(RecipeIngredient.item),
                )
                .order_by(Recipe.id)
            )
        )
        item_ids = {
            item_id
            for recipe in recipes
            for item_id in [
                recipe.crafted_item_id,
                *(ingredient.item_id for ingredient in recipe.ingredients),
            ]
            if item_id is not None
        }
        current_prices = self._prices.current_for_items(list(item_ids))
        rows: list[RecipeCatalogRow] = []
        for recipe in recipes:
            crafted_price = current_prices.get(recipe.crafted_item_id)
            metrics = calculate_recipe_metrics(
                None if crafted_price is None else crafted_price.unit_price,
                [
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
            rows.append(
                RecipeCatalogRow(
                    recipe_uuid=recipe.uuid,
                    item_uuid=recipe.crafted_item.uuid,
                    display_name=recipe.crafted_item.display_name,
                    category=recipe.crafted_item.category,
                    icon_url=(
                        None
                        if recipe.crafted_item.icon_source_url is None
                        else f"/item-icons/{recipe.crafted_item.uuid}.png"
                    ),
                    profession=recipe.profession,
                    profession_level=required_profession_level(len(recipe.ingredients)),
                    current_price=None if crafted_price is None else crafted_price.unit_price,
                    recipe_cost=metrics.recipe_cost,
                    profit=metrics.profit,
                    roi=metrics.roi,
                    is_complete=metrics.is_complete,
                )
            )
        return rows


def _filter_rows(
    rows: list[RecipeCatalogRow],
    filters: RecipeCatalogFilters,
) -> list[RecipeCatalogRow]:
    normalized_query = normalize_item_name(filters.item_query) if filters.item_query.strip() else ""
    normalized_category = normalize_item_name(filters.category) if filters.category.strip() else ""
    normalized_profession = filters.profession.strip().casefold()

    def matches(row: RecipeCatalogRow) -> bool:
        if normalized_query and normalized_query not in normalize_item_name(row.display_name):
            return False
        if normalized_category and (
            not row.category or normalize_item_name(row.category) != normalized_category
        ):
            return False
        if normalized_profession and row.profession.casefold() != normalized_profession:
            return False
        if filters.minimum_level is not None and (
            row.profession_level is None or row.profession_level < filters.minimum_level
        ):
            return False
        if filters.maximum_level is not None and (
            row.profession_level is None or row.profession_level > filters.maximum_level
        ):
            return False
        if filters.economics == "profitable":
            return row.profit is not None and row.profit > 0
        if filters.economics == "non_profitable":
            return row.profit is not None and row.profit <= 0
        if filters.economics == "unknown":
            return row.profit is None
        return True

    return [row for row in rows if matches(row)]


def _sort_rows(
    rows: list[RecipeCatalogRow],
    sort_field: RecipeSortField,
    sort_direction: RecipeSortDirection,
) -> list[RecipeCatalogRow]:
    def value(row: RecipeCatalogRow):
        if sort_field == "name":
            return row.display_name.casefold()
        if sort_field == "category":
            return None if row.category is None else row.category.casefold()
        if sort_field == "profession":
            return row.profession.casefold()
        if sort_field == "level":
            return row.profession_level
        if sort_field == "price":
            return row.current_price
        if sort_field == "cost":
            return row.recipe_cost
        if sort_field == "profit":
            return row.profit
        return row.roi

    with_value = [row for row in rows if value(row) is not None]
    without_value = [row for row in rows if value(row) is None]
    with_value.sort(key=lambda row: row.display_name.casefold())
    with_value.sort(key=value, reverse=sort_direction == "desc")
    without_value.sort(key=lambda row: row.display_name.casefold())
    return [*with_value, *without_value]
