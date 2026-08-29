with market_contexts as (
    select distinct market_context
    from {{ ref('stg_operational__price_observations') }}
),

recipe_ingredients_by_market as (
    select
        recipes.recipe_id,
        recipes.crafted_item_row_id,
        recipes.profession,
        ingredients.position as ingredient_position,
        ingredients.ingredient_item_row_id,
        ingredient_items.item_id as ingredient_item_id,
        ingredient_items.display_name as ingredient_item_name,
        ingredients.ingredient_raw_name,
        ingredients.ingredient_normalized_name,
        ingredients.quantity,
        market_contexts.market_context,
        recipes.ingestion_snapshot_id,
        recipes.warehouse_extracted_at
    from {{ ref('int_latest_recipes') }} as recipes
    inner join {{ ref('stg_operational__recipe_ingredients') }} as ingredients
        on recipes.recipe_row_id = ingredients.recipe_row_id
    left join {{ ref('stg_operational__items') }} as ingredient_items
        on ingredients.ingredient_item_row_id = ingredient_items.item_row_id
    cross join market_contexts
)

select
    recipe_ingredients.recipe_id,
    recipe_ingredients.crafted_item_row_id,
    recipe_ingredients.profession,
    recipe_ingredients.ingredient_position,
    recipe_ingredients.ingredient_item_row_id,
    recipe_ingredients.ingredient_item_id,
    recipe_ingredients.ingredient_item_name,
    recipe_ingredients.ingredient_raw_name,
    recipe_ingredients.ingredient_normalized_name,
    recipe_ingredients.quantity,
    recipe_ingredients.market_context,
    prices.price_observation_id as ingredient_price_observation_id,
    prices.unit_price as ingredient_unit_price,
    prices.observed_at as ingredient_price_observed_at,
    recipe_ingredients.ingestion_snapshot_id,
    recipe_ingredients.warehouse_extracted_at,
    recipe_ingredients.ingredient_item_id is not null as is_ingredient_resolved,
    prices.price_observation_id is not null as is_price_available,
    case
        when prices.unit_price is not null
            then recipe_ingredients.quantity * prices.unit_price
    end as extended_ingredient_cost
from recipe_ingredients_by_market as recipe_ingredients
left join {{ ref('int_latest_valid_price_observations') }} as prices
    on
        recipe_ingredients.ingredient_item_row_id = prices.item_row_id
        and recipe_ingredients.market_context = prices.market_context
