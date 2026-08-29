# dbt analyses

Store reusable analytical SQL that should compile with dbt but should not materialize as a warehouse model.

- `recipe_price_coverage.sql` reports the extent and type of incomplete current
  recipe costs by market and profession for engineering review.
