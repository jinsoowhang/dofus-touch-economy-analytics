# Session Notes 2026-08-29

## Analytics engineering fundamentals and recipe economics

### Context

Applied the dbt project-structure concepts from the user's Analytics Engineering
learning example through one locally executable transformation slice. The work was
explicitly credential-free and did not publish to or run against BigQuery.

### Work completed

- Added nine DuckDB-only synthetic seeds implementing the complete operational raw
  snapshot contract with 34 invented rows. The fixture covers two market contexts,
  complete ingredient pricing, a resolved ingredient without a price, an unresolved
  ingredient, and fallback from a newer invalidated observation.
- Added `int_recipe_ingredient_costs` at one latest-recipe ingredient position per
  market and `int_recipe_costs` at one latest recipe per market. The models preserve
  missing inputs, calculate price coverage, and emit a recipe cost only when every
  ingredient resolves and has a valid current price.
- Added `fct_recipe_economics` at one crafted item using its latest recipe per
  observed market. It exposes current item unit price, complete recipe cost,
  estimated profit, and estimated ROI as a ratio; incomplete inputs remain null.
- Added the non-materialized `recipe_price_coverage` analysis for engineering review
  by market and profession.
- Added six singular assertions for composite grains, ingredient-cost arithmetic,
  cost-status semantics, profit and ROI reconciliation, and the exact DuckDB fixture
  outcomes. Existing generic key, relationship, and accepted-value tests remain in
  the model YAML.
- Expanded the public local check sequence to seed the synthetic sources, run a full
  dbt build, and SQL-lint singular tests. Updated the public setup, architecture,
  ingestion guide, seed policy, model documentation, and agent commands.
- Added dbt's generated `dbt_internal_packages/` directory to both ignore and
  forbidden-public-file policy.

### Decisions

- Keep market context explicit in every recipe-cost and recipe-economics grain.
- Derive the set of observed markets from all staged observations, including markets
  whose current observations may all be invalidated, then use only latest valid
  observations for prices.
- Never treat an unresolved ingredient or missing price as zero. Recipe cost, profit,
  and ROI are available only when their required inputs are complete.
- Use seeds only for small invented DuckDB fixtures. BigQuery targets keep the seeds
  disabled and continue reading manifested private operational snapshots.
- Do not add dbt snapshots: operational snapshots are already immutable, recipes are
  versioned, and price observations are append-only.

### Verification

- Focused documented-command tests passed: 5 tests with the existing Starlette
  deprecation warning.
- Nine synthetic seeds loaded successfully, and dbt documentation generation wrote a
  complete catalog.
- The full local dbt build passed all 126 selected nodes: 18 models and 108 data tests,
  with no warnings, errors, or skips.
- Fixture reconciliation produced six expected mart rows. Synthetic Sword cost,
  profit, and ROI were 80, 920, and 11.5 in the primary market and 96, 804, and 8.375
  in the secondary market. Missing-price and unresolved recipes retained null costs
  and economics.
- `./scripts/check.sh` passed: Ruff lint and formatting, 256 Python tests, package
  compilation, dbt profile validation and parsing, nine seed loads, the 126-node dbt
  build, SQLFluff across models, analyses, and singular tests, and public-file policy.
  The Python suite retains the existing Starlette deprecation warning.
- No BigQuery snapshot publication, dbt Cloud build, or external credential use was
  performed.

### Next step

After review, publish the current operational snapshot and run the new graph in the
BigQuery development environment before considering a manual production build. A
later learning slice can model item-level sales performance from `fct_sales`.
