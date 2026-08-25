select
    id as sale_listing_row_id,
    uuid as sale_listing_id,
    item_id as item_row_id,
    price_observation_id as price_observation_row_id,
    lot_quantity,
    asking_price,
    selling_started_at,
    date_sold,
    recipe_cost_at_sale,
    _snapshot_id as ingestion_snapshot_id,
    _extracted_at as warehouse_extracted_at,
    case when date_sold is null then 'active' else 'sold' end as listing_status
from {{ source('operational', 'raw_sale_listings') }}
where _snapshot_id = {{ latest_operational_snapshot_id() }}
