select
    snapshot_id,
    extracted_at,
    source_schema_version,
    total_row_count,
    table_counts_json
from {{ source('operational', 'raw_snapshot_manifest') }}
