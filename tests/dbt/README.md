# Singular dbt tests

Store SQL tests for business invariants that cannot be expressed with generic schema tests. Python tests live in `tests/python/`.

Recipe-economics assertions protect the composite model grains, ingredient-cost
arithmetic, explicit incomplete-cost behavior, and profit and return-on-investment
definitions. A DuckDB-only assertion also reconciles all expected synthetic fixture
outcomes, including fallback from an invalidated observation.
