{% macro divide_whole_amount(numerator, denominator) -%}
    {{ return(adapter.dispatch('divide_whole_amount', 'dofus_touch_economy_analytics')(numerator, denominator)) }}
{%- endmacro %}

{% macro default__divide_whole_amount(numerator, denominator) -%}
    cast({{ numerator }} as decimal(38, 9))
    / nullif(cast({{ denominator }} as decimal(38, 9)), 0)
{%- endmacro %}

{% macro bigquery__divide_whole_amount(numerator, denominator) -%}
    cast({{ numerator }} as numeric)
    / nullif(cast({{ denominator }} as numeric), 0)
{%- endmacro %}
