with ranked_observations as (
    select
        price_observation_row_id,
        price_observation_id,
        item_row_id,
        lot_quantity,
        total_price,
        unit_price,
        observed_at,
        recorded_at,
        market_context,
        note,
        observation_source,
        ingestion_snapshot_id,
        warehouse_extracted_at,
        row_number() over (
            partition by item_row_id, market_context
            order by observed_at desc, recorded_at desc, price_observation_row_id desc
        ) as observation_rank
    from {{ ref('stg_operational__price_observations') }}
    where not is_invalidated
)

select
    price_observation_row_id,
    price_observation_id,
    item_row_id,
    lot_quantity,
    total_price,
    unit_price,
    observed_at,
    recorded_at,
    market_context,
    note,
    observation_source,
    ingestion_snapshot_id,
    warehouse_extracted_at
from ranked_observations
where observation_rank = 1
