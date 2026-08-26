# Session Notes 2026-08-25

## Item Detail Recipe Calculator Button

### Context

Fixed the Add to Recipe Calculator action on item detail pages after a reported item
exposed that the button had no active click handler.

### Work Completed

- Reproduced the browser parse failure by compiling the item detail page's two classic
  scripts in one global lexical scope.
- Found that `sales.js` and `recipe-cart.js` declared the same cart and selection
  storage-key constants, causing the second script to fail before binding its button
  handler.
- Gave the Sales cleanup script distinct top-level identifier names while preserving
  the existing browser storage keys and behavior.
- Added a static-asset regression test that prevents the two scripts from redeclaring
  those identifiers.

### Verification

- Combined-script compilation and individual JavaScript syntax checks passed.
- Six focused item-detail and recipe-cart tests passed.
- The full `./scripts/check.sh` sequence passed: Ruff lint and formatting, all 253
  Python tests, Python compilation, dbt debug and parse, SQLFluff, and the public-file
  policy.

## Selected Craft KPI Summary

### Context

Added a combined decision summary to Selected craft breakdown so the complete craft
batch can be evaluated without manually adding its row values.

### Work Completed

- Reused the existing responsive calculator KPI cards for Total Craft Quantity, Total
  Recipe Cost, Projected Sales, and Total Estimated Profit.
- Aggregated every displayed craft row independently of the Sell checkboxes, which
  remain controls only for the later Add Checked to Sales action.
- Recalculated Projected Sales and Total Estimated Profit immediately when any Sale
  Price Each input changes.
- Kept incomplete recipe-cost or sale-price coverage explicit instead of treating
  missing values as zero or presenting a partial total as complete.
- Added rendered-page and client-wiring regression coverage for initial combined
  values, live recalculation, and incomplete inputs.

### Verification

- Ten focused Recipe Calculator service, static-asset, and rendered-page tests passed.
- JavaScript syntax, Ruff lint and formatting, and diff checks passed.
- The full `./scripts/check.sh` sequence passed: all 253 Python tests, Python
  compilation, dbt debug and parse, SQLFluff, and the public-file policy.
