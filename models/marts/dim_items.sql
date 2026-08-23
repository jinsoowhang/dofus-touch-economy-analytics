select
    item_id,
    display_name,
    normalized_name,
    category,
    identity_category,
    created_source,
    icon_source_url,
    weight,
    created_at,
    updated_at,
    ingestion_snapshot_id,
    warehouse_extracted_at
from {{ ref('stg_operational__items') }}
