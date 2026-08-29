select
    recipe_id,
    market_context,
    ingredient_position
from {{ ref('int_recipe_ingredient_costs') }}
where
    is_ingredient_resolved <> (ingredient_item_id is not null)
    or is_price_available <> (ingredient_price_observation_id is not null)
    or (
        not is_price_available
        and (ingredient_unit_price is not null or extended_ingredient_cost is not null)
    )
    or (
        is_price_available
        and (
            ingredient_unit_price is null
            or extended_ingredient_cost is null
            or extended_ingredient_cost <> quantity * ingredient_unit_price
        )
    )
