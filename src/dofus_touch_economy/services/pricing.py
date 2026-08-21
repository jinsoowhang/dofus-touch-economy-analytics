from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class IngredientPrice:
    quantity: int
    unit_price: Decimal | None


@dataclass(frozen=True)
class RecipeMetrics:
    recipe_cost: Decimal | None
    profit: Decimal | None
    roi: Decimal | None
    is_complete: bool


def unit_price(total_price: int, lot_quantity: int) -> Decimal:
    if total_price <= 0 or lot_quantity <= 0:
        raise ValueError("price and quantity must be positive")
    return Decimal(total_price) / Decimal(lot_quantity)


def calculate_recipe_metrics(
    crafted_item_price: Decimal | None,
    ingredients: list[IngredientPrice],
) -> RecipeMetrics:
    if any(ingredient.unit_price is None for ingredient in ingredients):
        return RecipeMetrics(recipe_cost=None, profit=None, roi=None, is_complete=False)

    recipe_cost = sum(
        (
            Decimal(ingredient.quantity) * ingredient.unit_price
            for ingredient in ingredients
            if ingredient.unit_price is not None
        ),
        start=Decimal(0),
    )
    profit = None if crafted_item_price is None else crafted_item_price - recipe_cost
    roi = None if profit is None or recipe_cost == 0 else profit / recipe_cost
    return RecipeMetrics(recipe_cost=recipe_cost, profit=profit, roi=roi, is_complete=True)
