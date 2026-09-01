select
    sales.sale_listing_id,
    items.item_id,
    items.display_name as item_name,
    items.category as item_category,
    observations.price_observation_id,
    sales.lot_quantity,
    sales.asking_price,
    sales.selling_started_at,
    sales.date_sold,
    sales.recipe_cost_at_sale,
    sales.listing_source,
    sales.listing_capture_uuid,
    sales.sale_source,
    sales.sale_capture_uuid,
    sales.listing_status,
    sales.ingestion_snapshot_id,
    sales.warehouse_extracted_at,
    sales.asking_price - sales.recipe_cost_at_sale as profit_at_sale
from {{ ref('stg_operational__sale_listings') }} as sales
inner join {{ ref('stg_operational__items') }} as items
    on sales.item_row_id = items.item_row_id
left join {{ ref('stg_operational__price_observations') }} as observations
    on sales.price_observation_row_id = observations.price_observation_row_id
