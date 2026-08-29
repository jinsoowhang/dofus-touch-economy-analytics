select
    recipe_id,
    market_context,
    ingredient_position,
    count(*) as row_count
from {{ ref('int_recipe_ingredient_costs') }}
group by
    recipe_id,
    market_context,
    ingredient_position
having count(*) > 1
