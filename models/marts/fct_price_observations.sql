select
    observations.price_observation_id,
    items.item_id,
    items.display_name as item_name,
    items.category as item_category,
    observations.lot_quantity,
    observations.total_price,
    observations.unit_price,
    observations.observed_at,
    observations.recorded_at,
    observations.market_context,
    observations.note,
    observations.observation_source,
    observations.invalidated_at,
    observations.invalidation_reason,
    observations.is_invalidated,
    observations.ingestion_snapshot_id,
    observations.warehouse_extracted_at
from {{ ref('stg_operational__price_observations') }} as observations
inner join {{ ref('stg_operational__items') }} as items
    on observations.item_row_id = items.item_row_id
