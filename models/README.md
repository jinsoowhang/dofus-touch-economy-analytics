# dbt models

Every model must document its grain and primary analytical responsibility.

- `staging/`: source-oriented renaming, typing, and basic validation.
- `intermediate/`: reusable transformations and normalized business concepts.
- `marts/`: consumer-facing dimensions, facts, and governed measures.

Naming conventions:

- `stg_<source>__<entity>`
- `int_<description>`
- `dim_<entity>`
- `fct_<process>`

Domain models begin only after the source contracts and full dates are deterministic.
