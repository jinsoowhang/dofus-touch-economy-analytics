{% macro latest_operational_snapshot_id() %}
(
    select snapshot_id
    from {{ source('operational', 'raw_snapshot_manifest') }}
    order by extracted_at desc, snapshot_id desc
    limit 1
)
{% endmacro %}
