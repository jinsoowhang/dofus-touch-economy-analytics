select
    id as source_item_name_row_id,
    source_record_id as source_record_row_id,
    source_field,
    position,
    raw_name,
    normalized_name,
    item_id as item_row_id,
    resolution_status,
    _snapshot_id as ingestion_snapshot_id,
    _extracted_at as warehouse_extracted_at
from {{ source('operational', 'raw_source_item_names') }}
where _snapshot_id = {{ latest_operational_snapshot_id() }}
