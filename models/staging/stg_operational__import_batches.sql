select
    id as import_batch_row_id,
    uuid as import_batch_id,
    dataset as source_dataset,
    filename as source_filename,
    checksum as source_checksum,
    accepted_count,
    rejected_count,
    warning_count,
    status as import_status,
    started_at,
    completed_at,
    _snapshot_id as ingestion_snapshot_id,
    _extracted_at as warehouse_extracted_at
from {{ source('operational', 'raw_import_batches') }}
where _snapshot_id = {{ latest_operational_snapshot_id() }}
