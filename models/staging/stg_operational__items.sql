select
    id as item_row_id,
    uuid as item_id,
    display_name,
    normalized_name,
    category,
    identity_category,
    created_source,
    icon_source_url,
    weight,
    touch_catalog_status,
    touch_catalog_checked_at,
    touch_catalog_exclusion_reason,
    created_at,
    updated_at,
    _snapshot_id as ingestion_snapshot_id,
    _extracted_at as warehouse_extracted_at
from {{ source('operational', 'raw_items') }}
where _snapshot_id = {{ latest_operational_snapshot_id() }}
