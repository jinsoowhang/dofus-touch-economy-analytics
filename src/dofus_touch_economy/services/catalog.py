from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from dofus_touch_economy.repositories.catalog import CatalogRepository
from dofus_touch_economy.schemas import (
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
)


class CatalogService:
    def __init__(self, session: Session, market_context: str) -> None:
        self._catalog = CatalogRepository(session)
        self._prices = PriceService(session, market_context)
        self._market_context = market_context

    def search(self, query: str, limit: int = 50) -> list[ItemSummaryResponse]:
        return [
            ItemSummaryResponse(
                uuid=item.uuid,
                display_name=item.display_name,
                category=item.category,
            )
            for item in self._catalog.search(query, limit)
        ]

    def detail(self, item_uuid: UUID) -> ItemDetailResponse:
        item = self._catalog.get_by_uuid(item_uuid)
        if item is None:
            raise ItemNotFound(str(item_uuid))

        current_price = self._prices.current_for_item(item.id)
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
                ingredient_responses.append(
                    RecipeIngredientResponse(
                        position=ingredient.position,
                        item_uuid=None if ingredient.item is None else ingredient.item.uuid,
                        display_name=(
                            ingredient.raw_name
                            if ingredient.item is None
                            else ingredient.item.display_name
                        ),
                        raw_name=ingredient.raw_name,
                        quantity=ingredient.quantity,
                        current_price=ingredient_current,
                        extended_cost=extended_cost,
                        is_resolved=ingredient.item is not None,
                    )
                )
            recipe_metrics = calculate_recipe_metrics(
                crafted_item_price=None if current_price is None else current_price.unit_price,
                ingredients=ingredient_prices,
            )
            recipe_response = RecipeResponse(
                uuid=recipe.uuid,
                profession=recipe.profession,
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
            market_context=self._market_context,
            current_price=current_price,
            recipe=recipe_response,
            metrics=metrics_response,
            price_history=self._prices.history_for_item(item.id),
        )
