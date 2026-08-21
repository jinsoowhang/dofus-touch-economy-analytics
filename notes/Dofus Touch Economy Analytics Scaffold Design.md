# Dofus Touch Economy Analytics Scaffold Design

**Date:** 2026-08-20
**Status:** Approved through `grill-me-yolo`, with user overrides incorporated

## Summary

This project will be a public, reproducible analytics engineering repository for studying a player-observed Dofus Touch economy. Its public identity is the game-economy problem itself.

The first implementation milestone establishes the repository, local toolchain, data boundaries, and an empty but valid dbt project. It preserves the supplied source files locally without publishing them. Ingestion logic and analytical models follow in a separate milestone after the source date fields and contracts are made deterministic.

## Goals

- Establish a clean public repository named `dofus-touch-economy-analytics`.
- Use analytics engineering conventions recognizable to a new contributor.
- Make local setup reproducible with Python 3.12 and `uv`.
- Use dbt Core with DuckDB as the free local transformation stack.
- Protect raw source data, local databases, credentials, and private working files from Git.
- Define source, SQL, Python, documentation, testing, and naming conventions before models are added.
- Preserve the three supplied CSVs under concise canonical names.
- Preserve the legacy workbook locally without treating it as a canonical source.

## Non-goals for the scaffold milestone

- Building ingestion code or dbt domain models.
- Inferring missing years from abbreviated date strings.
- Publishing raw game-derived data.
- Deploying a cloud warehouse, Lightdash, an orchestrator, or an analytics agent.
- Automating collection from the game client or an Ankama website.
- Creating dashboards or notebooks.

## Approaches considered

### Python or notebooks only

This would be quick for exploration but would not establish a governed transformation layer, model lineage, schema tests, or semantic-ready documentation. It is not selected.

### Cloud-first warehouse and BI

A managed warehouse and Lightdash would resemble a production deployment, but they add credentials, cost, and infrastructure before the source contracts are stable. This is deferred.

### dbt Core and DuckDB

This is the selected approach. It supports modular SQL, tests, documentation, and repeatable local execution without external infrastructure. SQL should remain portable where practical so a future cloud target does not require a redesign.

## Source data

The user supplied three UTF-8 CSV exports. Their public canonical names will be:

- `item_sales.csv`: 998 source rows and 12 columns covering listing dates, sale dates, prices, costs, profit, reference values, estimates, and memos.
- `item_recipes.csv`: 296 source rows and 29 columns containing recipe outputs plus as many as eight repeated ingredient, quantity, and cost groups.
- `item_cost.csv`: 1,022 source rows and 3 columns containing item names, categories, and prices.

### Observed source constraints

- `item_sales.csv` has no stable transaction identifier or quantity field.
- Some date values are abbreviated, such as `11/24`, while others include a year.
- The full dates Excel may infer or display are not encoded in the CSV text.
- Numeric fields include thousands separators, percentages, `#N/A`, and `N/A`.
- Source files contain spreadsheet-calculated measures that must later be independently recomputed.
- The recipe export is a wide spreadsheet representation and contains rows without a recipe item or profession.
- Ingredient cost columns use zero when their corresponding ingredient and quantity are absent.
- Item cost names are not unique across the source file.

Date-dependent ingestion will require either a new export with ISO `YYYY-MM-DD` values or a source workbook that preserves the complete dates. The pipeline must not guess missing years.

## Architecture

The intended data flow is:

```text
Ignored source CSVs
        |
        v
Python contract validation and DuckDB loading (later milestone)
        |
        v
DuckDB raw schema
        |
        v
dbt staging -> intermediate -> marts
        |
        v
Governed metrics -> optional semantic layer and BI
```

Each boundary has one responsibility:

- Source storage preserves user-supplied files without modification.
- Ingestion validates file contracts and loads immutable raw tables.
- Staging models rename, type, and document source fields without business aggregation.
- Intermediate models normalize reusable concepts, including recipe ingredients.
- Marts expose dimensions, facts, and governed business measures.
- A semantic layer is added only after mart grains and metric definitions are stable.

## Repository layout

The dbt project will live at the repository root for simple commands and onboarding.

```text
.
├── .github/workflows/
├── analyses/
├── data/
│   ├── raw/
│   │   └── legacy/
│   ├── samples/
│   └── warehouse/
├── docs/
│   └── adr/
├── macros/
├── models/
│   ├── staging/
│   ├── intermediate/
│   └── marts/
├── notes/
├── seeds/
├── snapshots/
├── src/
├── tests/
├── AGENTS.md
├── dbt_project.yml
├── profiles.yml
├── pyproject.toml
└── README.md
```

Tracked README files will explain the purpose of otherwise empty directories. Raw CSVs, the legacy workbook, DuckDB files, dbt artifacts, secrets, and task-observer bookkeeping will be ignored.

## Data conventions

### Source files

- UTF-8 encoding with one header row and comma delimiters.
- Snake_case column names.
- ISO `YYYY-MM-DD` dates and explicit timezone-bearing timestamps when time is present.
- Explicit null representation rather than formula error strings.
- Immutable raw files; corrections arrive as new files or documented replacements.
- Source metadata will eventually include original filename, source row number, load time, observation time, and server or market context.

### Modeling

- Every model documents one grain.
- Candidate natural keys are profiled before surrogate keys are introduced.
- Prices and kama-denominated amounts use whole-number integer types.
- Item matching begins with trimmed exact names and a deterministic normalized form; fuzzy matching is excluded.
- Source categories remain unchanged until a governed mapping is approved.
- Duplicate item costs fail or quarantine validation rather than being silently selected.
- Raw spreadsheet calculations are preserved for reconciliation but are not canonical metrics.

### Naming

- Staging: `stg_<source>__<entity>`
- Intermediate: `int_<description>`
- Dimensions: `dim_<entity>`
- Facts: `fct_<process>`
- Python, SQL, YAML, and directory names use snake_case where their ecosystems allow it.

## Planned analytical model

The model design is directional until deterministic source dates are provided:

- A conformed item dimension assembled from sales items, recipe outputs, ingredients, and item costs.
- A sales fact at the source-row listing or sale-observation grain.
- A normalized recipe entity and recipe-ingredient bridge with one ingredient per row.
- Item cost observations that preserve duplicates until their business distinction is known.
- Governed measures for realized sale profit, listing-level days to sell, recipe cost, estimated crafting margin, and ROI.

Unit-level sell-through is excluded because the sales source has no quantity field. Listing-level sell-through may be considered after the row grain and unsold-row semantics are verified.

## Error handling and validation

- Raw values remain unchanged.
- Contract-breaking files fail before raw-table replacement.
- Invalid casts produce an explicit parse status or rejected-row record; they are never silently coerced.
- Rows without required business identifiers remain traceable to their source row but do not enter valid staging models.
- Derived measures are recalculated and reconciled against source values.
- Duplicate key candidates are surfaced through tests and profiling rather than resolved implicitly.

## Quality and testing

The toolchain will use:

- Ruff for Python linting and formatting.
- SQLFluff for dbt SQL style.
- dbt parsing in the scaffold milestone.
- dbt schema and singular tests once models exist.
- Pytest for ingestion contract tests once Python ingestion exists.
- Pre-commit hooks for fast local checks.
- GitHub Actions for locked dependency installation, configuration parsing, linting, and raw-data leakage checks.

The initial scaffold does not create fake domain models merely to make `dbt build` do work. Its meaningful dbt verification is successful project parsing and profile validation.

## Public repository safeguards

- Original CSVs and the legacy workbook are not committed.
- Only synthetic sample data may be committed until redistribution rights are established.
- The MIT license applies to original project code, not source data or third-party game material.
- The README identifies the repository as an unofficial fan analytics project and avoids official logos, artwork, or claims of affiliation.
- `.env`, credentials, local databases, logs, generated dbt artifacts, and private observer files are ignored from the first Git commit that introduces repository configuration.
- `MEMORY.md` and session notes contain only public-safe project decisions, verification, and next steps.

## Git strategy

Initialize a local Git repository without creating or pushing a remote. Commit the approved design independently. During implementation, keep executable scaffolding separate from public project documentation and session records so each commit is understandable and revertible.

## Scaffold acceptance criteria

The milestone is complete when:

1. The supplied files exist locally as ignored `data/raw/item_sales.csv`, `data/raw/item_recipes.csv`, and `data/raw/item_cost.csv`.
2. The legacy workbook exists locally under `data/raw/legacy/` and is ignored.
3. Public files use only the concise canonical dataset names.
4. `uv` can create the locked Python 3.12 environment.
5. dbt can validate its DuckDB profile and parse the empty project.
6. Configured lint and pre-commit checks pass.
7. GitHub Actions expresses the same repeatable repository checks without requiring raw data.
8. README and project documentation explain the purpose, architecture, data boundary, setup, and current limitations.
9. Project-specific `AGENTS.md`, `MEMORY.md`, and dated session notes reflect the approved conventions.
10. Git status contains no accidentally tracked raw data, databases, credentials, generated artifacts, or private observer files.

## Next milestone

Obtain deterministic full dates, finalize source contracts and row grains, implement test-driven ingestion into DuckDB, and then design and build staging models from the validated raw tables.
