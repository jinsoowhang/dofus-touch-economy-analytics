select
    recipe_id,
    market_context
from {{ ref('fct_recipe_economics') }}
where
    ingredient_count <= 0
    or resolved_ingredient_count < 0
    or resolved_ingredient_count > ingredient_count
    or priced_ingredient_count < 0
    or priced_ingredient_count > resolved_ingredient_count
    or price_coverage_ratio < 0
    or price_coverage_ratio > 1
    or abs(
        price_coverage_ratio
        - {{ divide_whole_amount('priced_ingredient_count', 'ingredient_count') }}
    ) > 0.000000001
    or (
        cost_status = 'complete'
        and (
            priced_ingredient_count <> ingredient_count
            or recipe_cost is null
            or recipe_cost <= 0
        )
    )
    or (
        cost_status = 'missing_price'
        and (
            resolved_ingredient_count <> ingredient_count
            or priced_ingredient_count >= ingredient_count
            or recipe_cost is not null
        )
    )
    or (
        cost_status = 'unresolved_ingredient'
        and (resolved_ingredient_count >= ingredient_count or recipe_cost is not null)
    )
    or (
        (recipe_cost is null or current_item_unit_price is null)
        and (
            estimated_profit is not null
            or estimated_return_on_investment is not null
        )
    )
    or (
        recipe_cost is not null
        and current_item_unit_price is not null
        and (
            estimated_profit is null
            or estimated_return_on_investment is null
            or estimated_profit <> current_item_unit_price - recipe_cost
            or estimated_return_on_investment
            <> {{ divide_whole_amount('estimated_profit', 'recipe_cost') }}
        )
    )
