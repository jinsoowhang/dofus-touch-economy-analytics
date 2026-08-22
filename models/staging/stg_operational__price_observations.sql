select
    id as price_observation_row_id,
    uuid as price_observation_id,
    item_id as item_row_id,
    lot_quantity,
    total_price,
    observed_at,
    recorded_at,
    market_context,
    note,
    source as observation_source,
    invalidated_at,
    invalidation_reason,
    _snapshot_id as ingestion_snapshot_id,
    _extracted_at as warehouse_extracted_at,
    {{ divide_whole_amount('total_price', 'lot_quantity') }} as unit_price,
    invalidated_at is not null as is_invalidated
from {{ source('operational', 'raw_price_observations') }}
where _snapshot_id = {{ latest_operational_snapshot_id() }}
