select
    recipe_costs.recipe_id,
    crafted_items.item_id as crafted_item_id,
    crafted_items.display_name as crafted_item_name,
    crafted_items.category as crafted_item_category,
    recipe_costs.profession,
    recipe_costs.market_context,
    recipe_costs.ingredient_count,
    recipe_costs.resolved_ingredient_count,
    recipe_costs.priced_ingredient_count,
    recipe_costs.price_coverage_ratio,
    recipe_costs.cost_status,
    recipe_costs.recipe_cost,
    current_prices.price_observation_id as current_item_price_observation_id,
    current_prices.unit_price as current_item_unit_price,
    current_prices.observed_at as current_item_price_observed_at,
    current_prices.recorded_at as current_item_price_recorded_at,
    case
        when recipe_costs.recipe_cost is not null and current_prices.unit_price is not null
            then current_prices.unit_price - recipe_costs.recipe_cost
    end as estimated_profit,
    case
        when recipe_costs.recipe_cost > 0 and current_prices.unit_price is not null
            then {{
                divide_whole_amount(
                    '(current_prices.unit_price - recipe_costs.recipe_cost)',
                    'recipe_costs.recipe_cost',
                )
            }}
    end as estimated_return_on_investment,
    recipe_costs.ingestion_snapshot_id,
    recipe_costs.warehouse_extracted_at
from {{ ref('int_recipe_costs') }} as recipe_costs
inner join {{ ref('stg_operational__items') }} as crafted_items
    on recipe_costs.crafted_item_row_id = crafted_items.item_row_id
left join {{ ref('int_latest_valid_price_observations') }} as current_prices
    on
        recipe_costs.crafted_item_row_id = current_prices.item_row_id
        and recipe_costs.market_context = current_prices.market_context
