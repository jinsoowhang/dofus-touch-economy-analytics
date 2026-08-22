select sale_listing_id
from {{ ref('fct_sales') }}
where date_sold < selling_started_at
