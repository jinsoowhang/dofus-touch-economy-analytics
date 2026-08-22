select
    id as recipe_row_id,
    uuid as recipe_id,
    crafted_item_id as crafted_item_row_id,
    profession,
    source_record_id as source_record_row_id,
    created_at,
    updated_at,
    _snapshot_id as ingestion_snapshot_id,
    _extracted_at as warehouse_extracted_at
from {{ source('operational', 'raw_recipes') }}
where _snapshot_id = {{ latest_operational_snapshot_id() }}
