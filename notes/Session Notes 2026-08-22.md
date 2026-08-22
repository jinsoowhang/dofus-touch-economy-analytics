# Session Notes 2026-08-22

## Context

Prepared the repository and account-side procedure for a BigQuery and free dbt
Developer hosted pilot. The user already has Google BigQuery and dbt accounts, but
the active environment has no authenticated Google Cloud CLI or external account
connector.

## Work Completed

- Confirmed from current official dbt documentation that free Developer accounts use
  service-account JSON authentication for BigQuery; BigQuery OAuth and workload
  identity federation require Enterprise-tier plans.
- Confirmed dbt's documented baseline roles are BigQuery Data Editor and BigQuery
  User, and chose a dedicated Google Cloud project to contain those project-level
  grants.
- Added a reproducible BigQuery, service-account, dbt connection, GitHub,
  environment, verification, and cost-control guide.
- Accepted an ADR for a hosted pilot that retains local dbt Core and DuckDB until
  model parity is demonstrated.
- Added `.secrets/` to Git ignore rules and the public-file policy, with a regression
  test for a BigQuery service-account key path.
- Updated the architecture, README, agent instructions, and memory.
- Mechanically formatted pre-existing Python snippets in the FastAPI implementation
  plan so the repository's full check could pass; this was committed separately from
  the hosted-pilot change.

## Decisions

- Use `dofus_dev` and `dofus_prod` as the BigQuery base datasets.
- Use dbt's Core `Latest` release track during the pilot rather than hosted BigQuery
  Fusion while Fusion support remains preview.
- Cap individual dbt queries at 1 GB processed and recommend a small BigQuery daily
  query quota.
- Use one single-purpose service account for development and deployment during the
  solo pilot, then separate identities before multi-user or production-sensitive
  use.
- Do not add placeholder dbt models or schedule a deployment job before deterministic
  ingestion and real models exist.
- Keep private raw exports local until a secure loader implements the approved source
  contract, metadata, and rejection behavior.

## Verification

- `uv run pytest tests/python/test_check_public_files.py -v` passed after the new
  `.secrets/` policy was implemented.
- `git diff --check` passed.
- `./scripts/check.sh` passed, including Ruff lint and formatting, Python tests, dbt
  debug and parse against local DuckDB, SQLFluff, and the public-file policy.
- GitHub authentication and the public repository URL were verified read-only.
- Hosted BigQuery connection, parse, and compile verification remain pending because
  account credentials are intentionally not available to this environment.

## Next Step

Use `docs/dbt-cloud-bigquery-setup.md` with the user's Google Cloud project ID and
dataset location, then confirm the dbt connection test plus hosted `dbt parse` and
`dbt compile`.
