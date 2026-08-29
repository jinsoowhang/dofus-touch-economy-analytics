# dbt seeds

Seeds are limited to small, stable, public reference datasets and explicitly
synthetic local-development fixtures. Raw source exports and production data do not
belong here.

`local_operational/` contains a minimal synthetic version of the operational
snapshot contract. Those seeds are enabled only when the dbt target uses DuckDB;
hosted BigQuery targets continue to read the immutable snapshots published by the
application loader.
