select
    market_context,
    profession,
    count(*) as recipe_count,
    sum(case when cost_status = 'complete' then 1 else 0 end) as complete_recipe_count,
    sum(case when cost_status = 'missing_price' then 1 else 0 end) as missing_price_count,
    sum(
        case when cost_status = 'unresolved_ingredient' then 1 else 0 end
    ) as unresolved_ingredient_count,
    avg(price_coverage_ratio) as average_price_coverage_ratio
from {{ ref('fct_recipe_economics') }}
group by
    market_context,
    profession
order by
    market_context,
    profession
