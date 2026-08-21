# Source data contract

## Shared rules

- Files are UTF-8 CSV with commas and one header row.
- Column names stay in stable `snake_case` within a dataset version.
- Dates use ISO `YYYY-MM-DD`.
- Timestamps use ISO 8601 with timezone.
- Kama-denominated values are whole numbers.
- Raw files are immutable inputs.
- Missing values must be empty or documented null representations, not spreadsheet error strings.

Current exports still contain abbreviated dates, formatted numerics, percentages, and spreadsheet errors. They are preserved locally but are not ingestion-ready until deterministic replacements or explicit parsing rules are approved.

## `item_sales`

Required columns in source order:

- `date`
- `item`
- `sold_date`
- `sold_price`
- `cost`
- `profit`
- `previous_price`
- `start_reference`
- `end_reference`
- `difference`
- `est_price_per_unit`
- `memo`

Provisional grain: one listing or sale observation per source row. The source does not provide a stable transaction identifier or quantity column.

## `item_recipes`

Leading columns:

- `recipe_item`
- `profession`

Repeated column groups:

- `raw_material_n`
- `quantity_n`
- `cost_n`

`n` runs from `1` through `8`. Preserve the wide raw layout as received, then normalize only populated groups in later transformations.

Trailing source measures:

- `total_cost`
- `profit`
- `ROI`

## `item_cost`

Columns:

- `raw_material`
- `category`
- `price`

Item names are not unique. Retain duplicates and report candidate-key violations rather than silently selecting one row.

## Required load metadata

- `source_file_name`
- `source_row_number`
- `loaded_at`
- `observed_at`
- server or market context

`observed_at` remains blocked until dates and collection context become deterministic.
