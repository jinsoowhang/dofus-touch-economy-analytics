select
    recipes.recipe_id,
    crafted_items.item_id as crafted_item_id,
    crafted_items.display_name as crafted_item_name,
    recipes.profession,
    ingredients.position as ingredient_position,
    ingredient_items.item_id as ingredient_item_id,
    ingredient_items.display_name as ingredient_item_name,
    ingredients.ingredient_raw_name,
    ingredients.ingredient_normalized_name,
    ingredients.quantity,
    recipes.ingestion_snapshot_id,
    recipes.warehouse_extracted_at,
    ingredient_items.item_id is not null as is_ingredient_resolved
from {{ ref('int_latest_recipes') }} as recipes
inner join {{ ref('stg_operational__items') }} as crafted_items
    on recipes.crafted_item_row_id = crafted_items.item_row_id
inner join {{ ref('stg_operational__recipe_ingredients') }} as ingredients
    on recipes.recipe_row_id = ingredients.recipe_row_id
left join {{ ref('stg_operational__items') }} as ingredient_items
    on ingredients.ingredient_item_row_id = ingredient_items.item_row_id
