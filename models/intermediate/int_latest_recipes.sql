with ranked_recipes as (
    select
        recipe_row_id,
        recipe_id,
        crafted_item_row_id,
        profession,
        source_record_row_id,
        created_at,
        updated_at,
        ingestion_snapshot_id,
        warehouse_extracted_at,
        row_number() over (
            partition by crafted_item_row_id
            order by created_at desc, updated_at desc, recipe_row_id desc
        ) as recipe_rank
    from {{ ref('stg_operational__recipes') }}
)

select
    recipe_row_id,
    recipe_id,
    crafted_item_row_id,
    profession,
    source_record_row_id,
    created_at,
    updated_at,
    ingestion_snapshot_id,
    warehouse_extracted_at
from ranked_recipes
where recipe_rank = 1
