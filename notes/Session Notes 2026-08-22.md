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

### Cloud Completion

- Installed the official Linux x86_64 Google Cloud CLI 581.0.0 under the WSL user
  directory after verifying Google's published SHA-256 checksum. The installation
  did not modify the repository or shell configuration.
- Completed browser-based user ADC authentication without putting a verification
  code or credential in chat, then assigned `claude-projects-489306` as the ADC quota
  project.
- Loaded snapshot
  `afc1d6b429721529f3468ae8f395f0541cc817c71f54e75537a58512af3113ea`
  into both `dofus_dev` and `dofus_prod`. Each manifest reports 67,266 source rows.
- Queried both datasets to verify `US` location, one manifest row, and exact per-table
  counts. An immediate loader rerun reported `already-loaded` for both datasets.
- The first guarded BigQuery `dbt build` exposed that BigQuery rejects parameterized
  decimal types inside `CAST`. Added an adapter-dispatched whole-amount division macro
  that retains `decimal(38, 9)` on DuckDB and uses unparameterized `numeric` on
  BigQuery.
- Reran the guarded BigQuery development build with dbt Core 1.12.0 and
  dbt-bigquery 1.12.0. All 15 models and 81 tests passed: 96/96 nodes, with no warnings,
  errors, or skips.
- Queried the development marts after the green build: 11,400 item rows, 1,138
  price-observation rows, 181 Sales rows, and 18,943 latest-recipe ingredient rows.
- Ran one guarded production build after the development result and cost check. All
  96 production nodes passed with no warnings, errors, or skips, and production mart
  counts exactly match development.
- The complete session used 4,660 MiB of billed query bytes across 306 recent query
  jobs, below the 0.01 TiB daily project quota. All raw and mart tables together use
  about 42.01 MiB of logical storage. The $10 budget remains alert-only, and no
  recurring job was scheduled.

### Next Step

Refresh dbt Studio so it sees the pushed model commit, run `dbt build` there to verify
the dbt Cloud execution path, then create a manual production deployment job only
after reviewing development lineage and costs.

## Public Project Description Refresh

### Work Completed

- Updated the public README to describe the implemented FastAPI, SQLite, BigQuery,
  and dbt architecture instead of an incomplete hosted pilot.
- Documented the exact manual snapshot command and clarified that website writes do
  not automatically update BigQuery or dbt models.
- Updated the GitHub profile project's Current Projects description to call this an
  economy tracker and analytics platform and to list the current primary stack.

### Verification

- Confirmed both repositories were clean before editing.
- `./scripts/check.sh` passed, including Ruff, 177 Python tests, package compilation,
  dbt debug and parse, SQLFluff, and the public-file policy.
- `git diff --check` passed in both repositories, and the profile entry appears
  exactly once in second position after `skills`.

## Local Item Icon Cache Recovery

### Cause and Repair

- The canonical SQLite database contained `icon_source_url` metadata for 11,390
  items, but the ignored `data/app/item_icons/` directory was absent. The UI therefore
  rendered local icon routes whose files returned 404.
- Ran `uv run dofus-fetch-icons --workers=8` to reconstruct the cache from the
  configured public sources. It restored 11,390 valid PNG files totaling 93 MB.
- Ten catalog entries have no downloadable upstream image and remain intentionally
  without an icon.
- Added the recovery command to the README because the cache is independent of the
  SQLite database and is not transferred with it.

### Verification

- Confirmed a cached file begins with the PNG signature.
- Confirmed the running FastAPI application serves a cached icon with HTTP 200,
  `image/png`, and a nonzero response body.

## Currently Selling Position and Bulk Actions

### Work Completed

- Added a `currently-selling` fragment to the individual Mark-as-sold redirect and
  saved/restored the exact scroll offset for Currently Selling row actions.
- Added accessible row checkboxes, a select-all checkbox, a live selected-row count,
  and Mark selected sold and Delete selected controls.
- Added one validated bulk endpoint and transactional service methods. A missing,
  stale, or already-sold selection fails before any selected row is changed.
- Kept Duplicate as a row-only operation to avoid accidentally creating many new
  listings. Bulk deletion requires explicit browser confirmation.
- Preserved both table sort settings through individual and bulk actions.

### Verification

- Focused Ruff checks passed.
- All 64 Sales service and web tests passed, including atomic bulk updates, bulk
  deletion, selection validation, redirect anchors, and scroll-restoration assets.
- `./scripts/check.sh` passed, including Ruff, all 180 Python tests, package
  compilation, dbt debug and parse, SQLFluff, and the public-file policy.
