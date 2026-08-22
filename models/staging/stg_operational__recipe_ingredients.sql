select
    id as recipe_ingredient_row_id,
    recipe_id as recipe_row_id,
    position,
    item_id as ingredient_item_row_id,
    raw_name as ingredient_raw_name,
    normalized_name as ingredient_normalized_name,
    quantity,
    _snapshot_id as ingestion_snapshot_id,
    _extracted_at as warehouse_extracted_at
from {{ source('operational', 'raw_recipe_ingredients') }}
where _snapshot_id = {{ latest_operational_snapshot_id() }}
