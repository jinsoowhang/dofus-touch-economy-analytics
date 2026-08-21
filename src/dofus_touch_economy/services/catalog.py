from decimal import Decimal
from difflib import SequenceMatcher
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from dofus_touch_economy.models import Item
from dofus_touch_economy.normalization import normalize_item_name
from dofus_touch_economy.repositories.catalog import CatalogRepository
from dofus_touch_economy.schemas import (
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
)


class CatalogItemConflict(RuntimeError):
    def __init__(self, candidates: list[ItemSummaryResponse]) -> None:
        super().__init__("catalog item identity already exists")
        self.candidates = candidates


class CatalogService:
    def __init__(self, session: Session, market_context: str) -> None:
        self._session = session
        self._catalog = CatalogRepository(session)
        self._prices = PriceService(session, market_context)
        self._market_context = market_context

    def search(self, query: str, limit: int = 50) -> list[ItemSummaryResponse]:
        return [_item_summary(item) for item in self._catalog.search(query, limit)]

    def suggest(self, query: str, limit: int = 5) -> list[ItemSummaryResponse]:
        if not query.strip():
            return []
        normalized_query = normalize_item_name(query)
        scored = [
            (
                SequenceMatcher(None, normalized_query, item.normalized_name).ratio(),
                item,
            )
            for item in self._catalog.suggestion_candidates()
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
        identity_category = (
            "" if command.category is None else normalize_item_name(command.category)
        )
        existing = self._conflicting_items(
            normalized_name,
            identity_category,
            category_was_supplied=command.category is not None,
        )
        if existing:
            raise CatalogItemConflict(existing)

        item = Item(
            display_name=command.display_name,
            normalized_name=normalized_name,
            category=command.category,
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
                category_was_supplied=command.category is not None,
            )
            if existing:
                raise CatalogItemConflict(existing) from None
            raise
        return self.detail(item.uuid)

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
            created_source=item.created_source,
            market_context=self._market_context,
            current_price=current_price,
            recipe=recipe_response,
            metrics=metrics_response,
            price_history=self._prices.history_for_item(item.id),
        )


def _item_summary(item: Item) -> ItemSummaryResponse:
    return ItemSummaryResponse(
        uuid=item.uuid,
        display_name=item.display_name,
        category=item.category,
        created_source=item.created_source,
    )
