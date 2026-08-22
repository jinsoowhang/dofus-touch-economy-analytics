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

## Operational BigQuery Ingestion

### Work Completed

- Located the latest normalized operational SQLite state in an ignored stale
  worktree and copied it through SQLite's backup API to the canonical ignored
  `data/app/dofus_touch.sqlite3` path without modifying the source database.
- Added an exact-schema snapshot extractor for import batches, source records, items,
  source-name resolutions, recipes, recipe ingredients, price observations, and
  application Sales listings.
- Added a BigQuery loader that content-addresses snapshots, creates partitioned and
  clustered raw tables, makes partial retries safe, and publishes the manifest last.
- Added BigQuery-backed dbt sources, nine staging models, two intermediate models,
  four marts, generic schema tests, and three domain invariant tests.
- Added an operator guide with local dry run, ADC authentication, upload commands,
  Google Cloud sidebar verification, dbt Studio build steps, and cost-control notes.
- Accepted ADR 0004 and updated the public architecture, data contract, setup guide,
  README, agent guidance, and memory.

### Decisions

- Load normalized operational SQLite state instead of manually uploading raw CSVs.
- Continue excluding ambiguous `item_sales.csv`; application `sale_listings` are the
  only hosted Sales source because they have stable IDs and deterministic timestamps.
- Load `dofus_dev` and `dofus_prod` by default so each dbt environment has an
  identical immutable source snapshot.
- Authenticate the local loader with user Application Default Credentials. Do not
  create or download another service-account key; dbt Cloud keeps its existing key.
- Keep production dbt execution manual until development builds and costs are
  verified repeatedly.

### Verification

- The canonical database dry run produced snapshot
  `afc1d6b429721529f3468ae8f395f0541cc817c71f54e75537a58512af3113ea`, schema
  version `0005`, and 67,266 normalized rows across the eight contracted tables.
- Five focused extractor and loader tests passed, including hash stability, schema
  drift rejection, no-credential dry run, manifest-last publication, and idempotent
  reruns.
- `dbt parse`, `dbt compile`, and SQLFluff passed for 15 models, 81 data tests, and
  nine sources.
- The first full check exposed and then received a fix for the documented entry-point
  expectation. The final `./scripts/check.sh` passed: Ruff lint and formatting, 177
  Python tests, package compilation, dbt debug and parse, SQLFluff, and the
  public-file policy.
- The actual BigQuery command stopped before changes because Google Application
  Default Credentials were unavailable. WSL has neither `gcloud` nor an existing ADC
  credential.

### Next Step

Install the Google Cloud CLI, run `gcloud auth application-default login` through the
user's browser, rerun `dofus-load-bigquery`, push the dbt project, and execute
`dbt build` in Studio development.
