{{ config(enabled=target.type == 'duckdb') }}

with expected (
    crafted_item_name,
    market_context,
    cost_status,
    recipe_cost,
    current_item_unit_price,
    estimated_profit,
    estimated_return_on_investment
) as (
    values
    (
        'Synthetic Amulet',
        'synthetic-primary',
        'unresolved_ingredient',
        cast(null as decimal(38, 9)),
        cast(800 as decimal(38, 9)),
        cast(null as decimal(38, 9)),
        cast(null as decimal(38, 9))
    ),
    ('Synthetic Amulet', 'synthetic-secondary', 'unresolved_ingredient', null, null, null, null),
    ('Synthetic Shield', 'synthetic-primary', 'missing_price', null, 500, null, null),
    ('Synthetic Shield', 'synthetic-secondary', 'missing_price', null, null, null, null),
    ('Synthetic Sword', 'synthetic-primary', 'complete', 80, 1000, 920, 11.5),
    ('Synthetic Sword', 'synthetic-secondary', 'complete', 96, 900, 804, 8.375)
),

actual as (
    select
        crafted_item_name,
        market_context,
        cost_status,
        recipe_cost,
        current_item_unit_price,
        estimated_profit,
        estimated_return_on_investment
    from {{ ref('fct_recipe_economics') }}
)

select
    coalesce(actual.crafted_item_name, expected.crafted_item_name) as crafted_item_name,
    coalesce(actual.market_context, expected.market_context) as market_context
from actual
full outer join expected
    on
        actual.crafted_item_name = expected.crafted_item_name
        and actual.market_context = expected.market_context
where
    actual.crafted_item_name is null
    or expected.crafted_item_name is null
    or actual.cost_status <> expected.cost_status
    or actual.recipe_cost is distinct from expected.recipe_cost
    or actual.current_item_unit_price is distinct from expected.current_item_unit_price
    or actual.estimated_profit is distinct from expected.estimated_profit
    or (
        actual.estimated_return_on_investment
        is distinct from expected.estimated_return_on_investment
    )
