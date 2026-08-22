select
    id as source_record_row_id,
    import_batch_id as import_batch_row_id,
    row_number as source_row_number,
    raw_payload_json,
    status as source_record_status,
    validation_messages_json,
    _snapshot_id as ingestion_snapshot_id,
    _extracted_at as warehouse_extracted_at
from {{ source('operational', 'raw_source_records') }}
where _snapshot_id = {{ latest_operational_snapshot_id() }}
