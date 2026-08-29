with aggregated_costs as (
    select
        recipe_id,
        crafted_item_row_id,
        profession,
        market_context,
        ingestion_snapshot_id,
        warehouse_extracted_at,
        count(*) as ingredient_count,
        sum(case when is_ingredient_resolved then 1 else 0 end) as resolved_ingredient_count,
        sum(case when is_price_available then 1 else 0 end) as priced_ingredient_count,
        sum(extended_ingredient_cost) as known_recipe_cost
    from {{ ref('int_recipe_ingredient_costs') }}
    group by
        recipe_id,
        crafted_item_row_id,
        profession,
        market_context,
        ingestion_snapshot_id,
        warehouse_extracted_at
)

select
    recipe_id,
    crafted_item_row_id,
    profession,
    market_context,
    ingredient_count,
    resolved_ingredient_count,
    priced_ingredient_count,
    ingestion_snapshot_id,
    warehouse_extracted_at,
    {{ divide_whole_amount('priced_ingredient_count', 'ingredient_count') }}
        as price_coverage_ratio,
    case
        when resolved_ingredient_count < ingredient_count then 'unresolved_ingredient'
        when priced_ingredient_count < ingredient_count then 'missing_price'
        else 'complete'
    end as cost_status,
    case
        when priced_ingredient_count = ingredient_count then known_recipe_cost
    end as recipe_cost
from aggregated_costs
