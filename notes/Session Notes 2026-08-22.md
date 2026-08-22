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
- `./scripts/check.sh` passed after synchronization, including Ruff lint and
  formatting, 172 Python tests, application compilation, dbt debug and parse against
  local DuckDB, SQLFluff, and the public-file policy.
- GitHub authentication and the public repository URL were verified read-only.
- Hosted BigQuery connection, parse, and compile verification remain pending because
  account credentials are intentionally not available to this environment.

## Next Step

Use `docs/dbt-cloud-bigquery-setup.md` with the user's Google Cloud project ID and
dataset location, then confirm the dbt connection test plus hosted `dbt parse` and
`dbt compile`.

## GitHub Synchronization

- The first push was rejected safely because `origin/main` had advanced.
- Fetched `origin/main` from the previously observed `2e6e06c` tip to `171ee1d`.
- Created rollback branch `backup-pre-origin-sync-20260822` at the pre-sync local tip.
- Reviewed the 64 incoming commits and their 87-file delta before applying changes.
- Replayed only the hosted-pilot commit onto the fetched remote tip. The local
  formatting commit was dropped because remote commit `8686785` already contained
  the same mechanical formatting.
- Resolved conflicts in `AGENTS.md`, `MEMORY.md`, `README.md`,
  `docs/architecture.md`, and `scripts/check_public_files.py` by preserving the
  completed FastAPI implementation and layering the hosted pilot onto it.
- Preserved SQLite as ADR 0002 and assigned the BigQuery pilot ADR 0003.
- The replayed hosted-pilot commit is `9a6caa5`.
