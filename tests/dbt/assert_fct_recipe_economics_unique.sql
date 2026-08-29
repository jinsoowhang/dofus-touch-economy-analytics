select
    recipe_id,
    market_context,
    count(*) as row_count
from {{ ref('fct_recipe_economics') }}
group by
    recipe_id,
    market_context
having count(*) > 1
