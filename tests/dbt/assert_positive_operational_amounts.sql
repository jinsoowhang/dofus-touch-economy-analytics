select
    price_observation_id as record_id,
    'price_observation' as record_type
from {{ ref('fct_price_observations') }}
where lot_quantity <= 0 or total_price <= 0

union all

select
    sale_listing_id as record_id,
    'sale_listing' as record_type
from {{ ref('fct_sales') }}
where lot_quantity <= 0 or asking_price <= 0
