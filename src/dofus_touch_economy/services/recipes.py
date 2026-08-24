from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from fractions import Fraction
from typing import Literal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased, selectinload

from dofus_touch_economy.models import Item, Recipe, RecipeIngredient, SaleListing
from dofus_touch_economy.normalization import format_item_display_name, normalize_item_name
from dofus_touch_economy.services.pricing import (
    IngredientPrice,
    PriceService,
    PriceStatus,
    calculate_recipe_metrics,
    price_freshness,
)

RecipeSortField = Literal[
    "name",
    "category",
    "profession",
    "level",
    "active",
    "price",
    "cost",
    "profit",
    "roi",
]
RecipeSortDirection = Literal["asc", "desc"]
RecipeEconomicsFilter = Literal["all", "profitable", "non_profitable", "unknown"]
ProfitOpportunitySignal = Literal["Improving", "Newly priced", "Profitable now"]
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
    active_listing_count: int
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
    filtered_count: int
    professions: list[str]
    categories: list[RecipeCategoryChoice]
    minimum_available_level: int
    maximum_available_level: int
    page: int
    page_size: int
    page_count: int


@dataclass(frozen=True)
class ProfitOpportunity:
    item_uuid: UUID
    display_name: str
    category: str | None
    icon_url: str | None
    profession: str
    profession_level: int | None
    signal: ProfitOpportunitySignal
    current_price: Decimal
    recipe_cost: Decimal
    profit: Decimal
    roi: Decimal
    previous_recipe_cost: Decimal | None
    previous_roi: Decimal | None
    roi_change: Decimal | None
    active_listing_count: int
    completed_sale_count: int


@dataclass(frozen=True)
class ProfitOpportunityReport:
    items: tuple[ProfitOpportunity, ...]
    total_count: int
    improving_count: int
    newly_priced_count: int
    top_profit_item: ProfitOpportunity | None
    top_roi_item: ProfitOpportunity | None


@dataclass(frozen=True)
class RecipeCalculatorChoice:
    item_uuid: UUID
    display_name: str
    category: str | None
    icon_url: str | None
    profession: str
    profession_level: int | None
    sale_price: int | None


@dataclass(frozen=True)
class RecipeCalculatorSuggestion:
    item_uuid: UUID
    display_name: str
    category: str | None
    icon_url: str | None
    profession: str
    profession_level: int | None
    shared_ingredient_count: int
    ingredient_count: int
    overlap_percent: int
    matching_selected_item_count: int


@dataclass(frozen=True)
class RecipeCalculatorSelectedItem:
    item_uuid: UUID
    display_name: str
    icon_url: str | None
    profession: str
    category: str | None
    profession_level: int | None
    craft_quantity: int
    recipe_unit_cost: Decimal | None
    total_recipe_cost: Decimal | None


@dataclass(frozen=True)
class RecipeCalculatorIngredient:
    item_uuid: UUID | None
    display_name: str
    category: str | None
    icon_url: str | None
    total_quantity: int
    unit_weight: int | None
    total_weight: int | None
    unit_price: Decimal | None
    total_cost: Decimal | None
    price_age_days: int | None
    price_status: PriceStatus
    used_by: tuple[str, ...]


@dataclass(frozen=True)
class RecipeCalculatorResult:
    selected_items: tuple[RecipeCalculatorSelectedItem, ...]
    ingredients: tuple[RecipeCalculatorIngredient, ...]
    total_crafts: int
    priced_ingredient_count: int
    known_total_cost: Decimal
    total_cost: Decimal | None
    weighted_ingredient_count: int
    known_total_weight: int
    total_weight: int | None


class RecipeCalculatorSelectionError(ValueError):
    pass


@dataclass
class _IngredientAccumulator:
    item_uuid: UUID | None
    display_name: str
    category: str | None
    icon_url: str | None
    total_quantity: int
    unit_weight: int | None
    unit_price: Decimal | None
    price_age_days: int | None
    price_status: PriceStatus
    used_by: set[str]


@dataclass
class _CatalogRecipe:
    recipe_uuid: UUID
    crafted_item_id: int
    item_uuid: UUID
    display_name: str
    category: str | None
    icon_source_url: str | None
    profession: str
    ingredients: list[tuple[int | None, str, int]]


class RecipeCatalogService:
    def __init__(self, session: Session, market_context: str) -> None:
        self._session = session
        self._prices = PriceService(session, market_context)

    def browse(
        self,
        filters: RecipeCatalogFilters | None = None,
        sort_field: RecipeSortField = "name",
        sort_direction: RecipeSortDirection = "asc",
        *,
        page: int = 1,
        page_size: int = 100,
    ) -> RecipeCatalogResult:
        if page < 1 or page_size < 1:
            raise ValueError("page and page size must be positive")
        rows = self._rows()
        levels = [row.profession_level for row in rows if row.profession_level is not None]
        category_labels: dict[str, str] = {}
        for row in rows:
            if row.category:
                key = normalize_item_name(row.category)
                category_labels.setdefault(key, format_item_display_name(row.category))
        filtered_rows = _filter_rows(rows, filters or RecipeCatalogFilters())
        ordered_rows = _sort_rows(filtered_rows, sort_field, sort_direction)
        page_count = max(1, (len(ordered_rows) + page_size - 1) // page_size)
        resolved_page = min(page, page_count)
        page_start = (resolved_page - 1) * page_size
        return RecipeCatalogResult(
            rows=ordered_rows[page_start : page_start + page_size],
            total_count=len(rows),
            filtered_count=len(ordered_rows),
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
            page=resolved_page,
            page_size=page_size,
            page_count=page_count,
        )

    def profit_opportunities(
        self,
        *,
        limit: int = 100,
        not_currently_selling: bool = False,
    ) -> ProfitOpportunityReport:
        if limit < 1:
            raise ValueError("limit must be positive")
        recipes = _latest_recipe_catalog(self._session)
        priced_item_ids = {
            item_id
            for recipe in recipes
            for item_id in [
                recipe.crafted_item_id,
                *(item_id for item_id, _normalized_name, _quantity in recipe.ingredients),
            ]
            if item_id is not None
        }
        prices = self._prices.current_and_previous_for_items(priced_item_ids)
        crafted_item_ids = {recipe.crafted_item_id for recipe in recipes}
        active_listing_counts = dict(
            self._session.execute(
                select(SaleListing.item_id, func.count(SaleListing.id))
                .where(
                    SaleListing.item_id.in_(crafted_item_ids),
                    SaleListing.date_sold.is_(None),
                )
                .group_by(SaleListing.item_id)
            )
            .tuples()
            .all()
        )
        completed_sale_counts = dict(
            self._session.execute(
                select(SaleListing.item_id, func.count(SaleListing.id))
                .where(
                    SaleListing.item_id.in_(crafted_item_ids),
                    SaleListing.date_sold.is_not(None),
                )
                .group_by(SaleListing.item_id)
            )
            .tuples()
            .all()
        )

        opportunities: list[ProfitOpportunity] = []
        for recipe in recipes:
            crafted_item_price = prices.get(recipe.crafted_item_id)
            if crafted_item_price is None:
                continue
            current_metrics = calculate_recipe_metrics(
                crafted_item_price.current.unit_price,
                [
                    IngredientPrice(
                        quantity=quantity,
                        unit_price=(
                            None
                            if item_id is None or item_id not in prices
                            else prices[item_id].current.unit_price
                        ),
                    )
                    for item_id, _normalized_name, quantity in recipe.ingredients
                ],
            )
            if (
                current_metrics.recipe_cost is None
                or current_metrics.profit is None
                or current_metrics.roi is None
                or current_metrics.profit <= 0
            ):
                continue

            previous_metrics = calculate_recipe_metrics(
                crafted_item_price.current.unit_price,
                [
                    IngredientPrice(
                        quantity=quantity,
                        unit_price=(
                            None
                            if item_id is None
                            or item_id not in prices
                            or prices[item_id].previous is None
                            else prices[item_id].previous.unit_price
                        ),
                    )
                    for item_id, _normalized_name, quantity in recipe.ingredients
                ],
            )
            previous_roi = previous_metrics.roi
            roi_change = None if previous_roi is None else current_metrics.roi - previous_roi
            if previous_metrics.recipe_cost is None:
                signal: ProfitOpportunitySignal = "Newly priced"
            elif roi_change is not None and roi_change > 0:
                signal = "Improving"
            else:
                signal = "Profitable now"
            opportunities.append(
                ProfitOpportunity(
                    item_uuid=recipe.item_uuid,
                    display_name=recipe.display_name,
                    category=recipe.category,
                    icon_url=(
                        None
                        if recipe.icon_source_url is None
                        else f"/item-icons/{recipe.item_uuid}.png"
                    ),
                    profession=recipe.profession,
                    profession_level=required_profession_level(len(recipe.ingredients)),
                    signal=signal,
                    current_price=crafted_item_price.current.unit_price,
                    recipe_cost=current_metrics.recipe_cost,
                    profit=current_metrics.profit,
                    roi=current_metrics.roi,
                    previous_recipe_cost=previous_metrics.recipe_cost,
                    previous_roi=previous_roi,
                    roi_change=roi_change,
                    active_listing_count=active_listing_counts.get(
                        recipe.crafted_item_id,
                        0,
                    ),
                    completed_sale_count=completed_sale_counts.get(
                        recipe.crafted_item_id,
                        0,
                    ),
                )
            )

        if not_currently_selling:
            opportunities = [item for item in opportunities if item.active_listing_count == 0]
        signal_order: dict[ProfitOpportunitySignal, int] = {
            "Improving": 0,
            "Newly priced": 1,
            "Profitable now": 2,
        }
        opportunities.sort(
            key=lambda item: (
                signal_order[item.signal],
                -(item.roi_change if item.signal == "Improving" else item.roi),
                -item.roi,
                -item.profit,
                item.display_name.casefold(),
            )
        )
        return ProfitOpportunityReport(
            items=tuple(opportunities[:limit]),
            total_count=len(opportunities),
            improving_count=sum(item.signal == "Improving" for item in opportunities),
            newly_priced_count=sum(item.signal == "Newly priced" for item in opportunities),
            top_profit_item=max(
                opportunities,
                key=lambda item: (item.profit, item.roi, item.display_name.casefold()),
                default=None,
            ),
            top_roi_item=max(
                opportunities,
                key=lambda item: (item.roi, item.profit, item.display_name.casefold()),
                default=None,
            ),
        )

    def _rows(self) -> list[RecipeCatalogRow]:
        recipes = _latest_recipe_catalog(self._session)
        item_ids = {
            item_id
            for recipe in recipes
            for item_id in [
                recipe.crafted_item_id,
                *(item_id for item_id, _normalized_name, _quantity in recipe.ingredients),
            ]
            if item_id is not None
        }
        current_prices = self._prices.current_for_items(list(item_ids))
        crafted_item_ids = {recipe.crafted_item_id for recipe in recipes}
        active_listing_counts = dict(
            self._session.execute(
                select(SaleListing.item_id, func.count(SaleListing.id))
                .where(
                    SaleListing.item_id.in_(crafted_item_ids),
                    SaleListing.date_sold.is_(None),
                )
                .group_by(SaleListing.item_id)
            )
            .tuples()
            .all()
        )
        rows: list[RecipeCatalogRow] = []
        for recipe in recipes:
            crafted_price = current_prices.get(recipe.crafted_item_id)
            metrics = calculate_recipe_metrics(
                None if crafted_price is None else crafted_price.unit_price,
                [
                    IngredientPrice(
                        quantity=quantity,
                        unit_price=(
                            None
                            if item_id is None or item_id not in current_prices
                            else current_prices[item_id].unit_price
                        ),
                    )
                    for item_id, _normalized_name, quantity in recipe.ingredients
                ],
            )
            rows.append(
                RecipeCatalogRow(
                    recipe_uuid=recipe.recipe_uuid,
                    item_uuid=recipe.item_uuid,
                    display_name=recipe.display_name,
                    category=recipe.category,
                    icon_url=(
                        None
                        if recipe.icon_source_url is None
                        else f"/item-icons/{recipe.item_uuid}.png"
                    ),
                    profession=recipe.profession,
                    profession_level=required_profession_level(len(recipe.ingredients)),
                    active_listing_count=active_listing_counts.get(
                        recipe.crafted_item_id,
                        0,
                    ),
                    current_price=None if crafted_price is None else crafted_price.unit_price,
                    recipe_cost=metrics.recipe_cost,
                    profit=metrics.profit,
                    roi=metrics.roi,
                    is_complete=metrics.is_complete,
                )
            )
        return rows


class RecipeCalculatorService:
    def __init__(
        self,
        session: Session,
        market_context: str,
        *,
        as_of: datetime | None = None,
    ) -> None:
        self._session = session
        self._prices = PriceService(session, market_context)
        self._as_of = as_of or datetime.now(UTC)

    def choices(self) -> list[RecipeCalculatorChoice]:
        recipes = _latest_recipe_catalog(self._session)
        current_prices = self._prices.current_for_items(
            [recipe.crafted_item_id for recipe in recipes]
        )
        return sorted(
            (
                RecipeCalculatorChoice(
                    item_uuid=recipe.item_uuid,
                    display_name=recipe.display_name,
                    category=recipe.category,
                    icon_url=(
                        None
                        if recipe.icon_source_url is None
                        else f"/item-icons/{recipe.item_uuid}.png"
                    ),
                    profession=recipe.profession,
                    profession_level=required_profession_level(len(recipe.ingredients)),
                    sale_price=(
                        None
                        if (
                            (current_price := current_prices.get(recipe.crafted_item_id)) is None
                            or current_price.unit_price
                            != current_price.unit_price.to_integral_value()
                        )
                        else int(current_price.unit_price)
                    ),
                )
                for recipe in recipes
            ),
            key=lambda choice: choice.display_name.casefold(),
        )

    def suggest_similar(
        self,
        selected_item_uuids: tuple[UUID, ...],
        *,
        limit: int = 10,
    ) -> list[RecipeCalculatorSuggestion]:
        if len(selected_item_uuids) < 2:
            raise RecipeCalculatorSelectionError(
                "Select at least two craftable items to get suggestions."
            )
        if len(selected_item_uuids) > 100:
            raise RecipeCalculatorSelectionError("Select no more than 100 craftable items.")
        if len(set(selected_item_uuids)) != len(selected_item_uuids):
            raise RecipeCalculatorSelectionError("A craftable item was selected more than once.")
        if limit < 1:
            return []

        recipes = _latest_recipe_catalog(self._session)
        recipes_by_item_uuid = {recipe.item_uuid: recipe for recipe in recipes}
        missing = set(selected_item_uuids).difference(recipes_by_item_uuid)
        if missing:
            raise RecipeCalculatorSelectionError(
                "One or more selected items no longer has a current recipe."
            )

        selected_ingredient_keys = {
            item_uuid: {
                _catalog_ingredient_key(item_id, normalized_name)
                for item_id, normalized_name, _quantity in recipes_by_item_uuid[
                    item_uuid
                ].ingredients
            }
            for item_uuid in selected_item_uuids
        }
        combined_ingredient_keys = set().union(*selected_ingredient_keys.values())
        selected_item_uuid_set = set(selected_item_uuids)
        ranked_suggestions: list[tuple[Fraction, int, int, RecipeCalculatorSuggestion]] = []
        for recipe in recipes:
            if recipe.item_uuid in selected_item_uuid_set or not recipe.ingredients:
                continue
            ingredient_keys = [
                _catalog_ingredient_key(item_id, normalized_name)
                for item_id, normalized_name, _quantity in recipe.ingredients
            ]
            shared_ingredient_count = sum(
                ingredient_key in combined_ingredient_keys for ingredient_key in ingredient_keys
            )
            if shared_ingredient_count == 0:
                continue
            candidate_ingredient_keys = set(ingredient_keys)
            matching_selected_item_count = sum(
                bool(candidate_ingredient_keys.intersection(selected_keys))
                for selected_keys in selected_ingredient_keys.values()
            )
            ingredient_count = len(ingredient_keys)
            overlap = Fraction(shared_ingredient_count, ingredient_count)
            suggestion = RecipeCalculatorSuggestion(
                item_uuid=recipe.item_uuid,
                display_name=recipe.display_name,
                category=recipe.category,
                icon_url=(
                    None
                    if recipe.icon_source_url is None
                    else f"/item-icons/{recipe.item_uuid}.png"
                ),
                profession=recipe.profession,
                profession_level=required_profession_level(len(recipe.ingredients)),
                shared_ingredient_count=shared_ingredient_count,
                ingredient_count=ingredient_count,
                overlap_percent=(shared_ingredient_count * 100 + ingredient_count // 2)
                // ingredient_count,
                matching_selected_item_count=matching_selected_item_count,
            )
            ranked_suggestions.append(
                (
                    overlap,
                    shared_ingredient_count,
                    matching_selected_item_count,
                    suggestion,
                )
            )

        ranked_suggestions.sort(key=lambda ranked: ranked[3].display_name.casefold())
        ranked_suggestions.sort(
            key=lambda ranked: (ranked[0], ranked[1], ranked[2]),
            reverse=True,
        )
        return [ranked[3] for ranked in ranked_suggestions[:limit]]

    def calculate(self, selections: dict[UUID, int]) -> RecipeCalculatorResult:
        if not selections:
            raise RecipeCalculatorSelectionError("Select at least one craftable item.")
        if len(selections) > 100:
            raise RecipeCalculatorSelectionError("Select no more than 100 craftable items.")
        if any(quantity < 1 or quantity > 1000 for quantity in selections.values()):
            raise RecipeCalculatorSelectionError("Each craft quantity must be between 1 and 1,000.")

        recipes_by_item_uuid = {
            recipe.crafted_item.uuid: recipe
            for recipe in _latest_recipes_for_items(self._session, tuple(selections))
        }
        missing = set(selections).difference(recipes_by_item_uuid)
        if missing:
            raise RecipeCalculatorSelectionError(
                "One or more selected items no longer has a current recipe."
            )
        selected_recipes = sorted(
            (recipes_by_item_uuid[item_uuid] for item_uuid in selections),
            key=lambda recipe: recipe.crafted_item.display_name.casefold(),
        )
        ingredient_item_ids = {
            ingredient.item_id
            for recipe in selected_recipes
            for ingredient in recipe.ingredients
            if ingredient.item_id is not None
        }
        current_prices = self._prices.current_for_items(list(ingredient_item_ids))

        selected_items: list[RecipeCalculatorSelectedItem] = []
        accumulated_ingredients: dict[tuple[str, object], _IngredientAccumulator] = {}
        for recipe in selected_recipes:
            craft_quantity = selections[recipe.crafted_item.uuid]
            ingredient_prices = [
                IngredientPrice(
                    quantity=ingredient.quantity,
                    unit_price=(
                        None
                        if ingredient.item_id is None or ingredient.item_id not in current_prices
                        else current_prices[ingredient.item_id].unit_price
                    ),
                )
                for ingredient in recipe.ingredients
            ]
            recipe_metrics = calculate_recipe_metrics(None, ingredient_prices)
            selected_items.append(
                RecipeCalculatorSelectedItem(
                    item_uuid=recipe.crafted_item.uuid,
                    display_name=recipe.crafted_item.display_name,
                    icon_url=_icon_url(recipe.crafted_item),
                    profession=recipe.profession,
                    category=recipe.crafted_item.category,
                    profession_level=required_profession_level(len(recipe.ingredients)),
                    craft_quantity=craft_quantity,
                    recipe_unit_cost=recipe_metrics.recipe_cost,
                    total_recipe_cost=(
                        None
                        if recipe_metrics.recipe_cost is None
                        else recipe_metrics.recipe_cost * craft_quantity
                    ),
                )
            )

            for ingredient in recipe.ingredients:
                if ingredient.item is None:
                    key: tuple[str, object] = ("unresolved", ingredient.normalized_name)
                    item_uuid = None
                    display_name = ingredient.raw_name
                    category = None
                    icon_url = None
                    unit_weight = None
                    unit_price = None
                    price_age_days, price_status = price_freshness(None, self._as_of)
                else:
                    key = ("item", ingredient.item_id)
                    item_uuid = ingredient.item.uuid
                    display_name = ingredient.item.display_name
                    category = ingredient.item.category
                    icon_url = _icon_url(ingredient.item)
                    unit_weight = ingredient.item.weight
                    current_price = current_prices.get(ingredient.item_id)
                    unit_price = None if current_price is None else current_price.unit_price
                    price_age_days, price_status = price_freshness(
                        current_price,
                        self._as_of,
                    )
                required_quantity = ingredient.quantity * craft_quantity
                existing = accumulated_ingredients.get(key)
                if existing is None:
                    accumulated_ingredients[key] = _IngredientAccumulator(
                        item_uuid=item_uuid,
                        display_name=display_name,
                        category=category,
                        icon_url=icon_url,
                        total_quantity=required_quantity,
                        unit_weight=unit_weight,
                        unit_price=unit_price,
                        price_age_days=price_age_days,
                        price_status=price_status,
                        used_by={recipe.crafted_item.display_name},
                    )
                else:
                    existing.total_quantity += required_quantity
                    existing.used_by.add(recipe.crafted_item.display_name)

        ingredients = tuple(
            RecipeCalculatorIngredient(
                item_uuid=ingredient.item_uuid,
                display_name=ingredient.display_name,
                category=ingredient.category,
                icon_url=ingredient.icon_url,
                total_quantity=ingredient.total_quantity,
                unit_weight=ingredient.unit_weight,
                total_weight=(
                    None
                    if ingredient.unit_weight is None
                    else ingredient.unit_weight * ingredient.total_quantity
                ),
                unit_price=ingredient.unit_price,
                total_cost=(
                    None
                    if ingredient.unit_price is None
                    else ingredient.unit_price * ingredient.total_quantity
                ),
                price_age_days=ingredient.price_age_days,
                price_status=ingredient.price_status,
                used_by=tuple(sorted(ingredient.used_by, key=str.casefold)),
            )
            for ingredient in sorted(
                accumulated_ingredients.values(),
                key=lambda ingredient: ingredient.display_name.casefold(),
            )
        )
        known_total_cost = sum(
            (
                ingredient.total_cost
                for ingredient in ingredients
                if ingredient.total_cost is not None
            ),
            start=Decimal(0),
        )
        priced_ingredient_count = sum(
            ingredient.total_cost is not None for ingredient in ingredients
        )
        known_total_weight = sum(
            (
                ingredient.total_weight
                for ingredient in ingredients
                if ingredient.total_weight is not None
            ),
            start=0,
        )
        weighted_ingredient_count = sum(
            ingredient.total_weight is not None for ingredient in ingredients
        )
        return RecipeCalculatorResult(
            selected_items=tuple(selected_items),
            ingredients=ingredients,
            total_crafts=sum(selections.values()),
            priced_ingredient_count=priced_ingredient_count,
            known_total_cost=known_total_cost,
            total_cost=(known_total_cost if priced_ingredient_count == len(ingredients) else None),
            weighted_ingredient_count=weighted_ingredient_count,
            known_total_weight=known_total_weight,
            total_weight=(
                known_total_weight if weighted_ingredient_count == len(ingredients) else None
            ),
        )


def _latest_recipe_ids():
    return (
        select(func.max(Recipe.id).label("recipe_id")).group_by(Recipe.crafted_item_id).subquery()
    )


def _latest_recipe_catalog(session: Session) -> list[_CatalogRecipe]:
    crafted_item = aliased(Item)
    latest_recipe_ids = _latest_recipe_ids()
    rows = session.execute(
        select(
            Recipe.id.label("recipe_id"),
            Recipe.uuid.label("recipe_uuid"),
            Recipe.crafted_item_id,
            Recipe.profession,
            crafted_item.uuid.label("item_uuid"),
            crafted_item.display_name,
            crafted_item.category,
            crafted_item.icon_source_url,
            RecipeIngredient.id.label("ingredient_id"),
            RecipeIngredient.item_id.label("ingredient_item_id"),
            RecipeIngredient.normalized_name.label("ingredient_normalized_name"),
            RecipeIngredient.quantity.label("ingredient_quantity"),
        )
        .join(latest_recipe_ids, latest_recipe_ids.c.recipe_id == Recipe.id)
        .join(crafted_item, crafted_item.id == Recipe.crafted_item_id)
        .outerjoin(RecipeIngredient, RecipeIngredient.recipe_id == Recipe.id)
        .order_by(Recipe.id, RecipeIngredient.position)
    )
    recipes_by_id: dict[int, _CatalogRecipe] = {}
    for row in rows:
        recipe = recipes_by_id.get(row.recipe_id)
        if recipe is None:
            recipe = _CatalogRecipe(
                recipe_uuid=row.recipe_uuid,
                crafted_item_id=row.crafted_item_id,
                item_uuid=row.item_uuid,
                display_name=row.display_name,
                category=row.category,
                icon_source_url=row.icon_source_url,
                profession=row.profession,
                ingredients=[],
            )
            recipes_by_id[row.recipe_id] = recipe
        if row.ingredient_id is not None:
            recipe.ingredients.append(
                (
                    row.ingredient_item_id,
                    row.ingredient_normalized_name,
                    row.ingredient_quantity,
                )
            )
    return list(recipes_by_id.values())


def _catalog_ingredient_key(item_id: int | None, normalized_name: str) -> tuple[str, object]:
    if item_id is not None:
        return ("item", item_id)
    return ("unresolved", normalized_name)


def _latest_recipes_for_items(session: Session, item_uuids: tuple[UUID, ...]) -> list[Recipe]:
    if not item_uuids:
        return []
    latest_recipe_ids = (
        select(func.max(Recipe.id).label("recipe_id"))
        .group_by(Recipe.crafted_item_id)
        .scalar_subquery()
    )
    return list(
        session.scalars(
            select(Recipe)
            .join(Recipe.crafted_item)
            .where(Recipe.id.in_(latest_recipe_ids), Item.uuid.in_(item_uuids))
            .options(
                selectinload(Recipe.crafted_item),
                selectinload(Recipe.ingredients).selectinload(RecipeIngredient.item),
            )
            .order_by(Recipe.id)
        )
    )


def _icon_url(item) -> str | None:
    return None if item.icon_source_url is None else f"/item-icons/{item.uuid}.png"


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
        if sort_field == "active":
            return row.active_listing_count
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
