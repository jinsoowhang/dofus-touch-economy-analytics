select
    recipe_id,
    ingredient_position,
    count(*) as row_count
from {{ ref('fct_recipe_ingredients') }}
group by recipe_id, ingredient_position
having count(*) > 1
