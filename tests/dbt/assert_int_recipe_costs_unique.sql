select
    recipe_id,
    market_context,
    count(*) as row_count
from {{ ref('int_recipe_costs') }}
group by
    recipe_id,
    market_context
having count(*) > 1
