# ADR 0003: Pilot dbt platform and BigQuery

- Status: Accepted
- Date: 2026-08-22

## Context

The project wants hosted dbt development and orchestration while preserving its
public, reproducible, local-first workflow. The current analytical database is a
machine-local DuckDB file. Hosted dbt does not offer DuckDB as a platform connection,
so adopting the dbt platform also requires a supported hosted data platform.

The repository has no dbt domain models or deterministic private-data ingestion into
an analytical warehouse yet. Replacing the local stack immediately would remove a
verified workflow before the hosted replacement can demonstrate parity.

## Decision

Pilot a free single-user dbt Developer project connected to BigQuery and the GitHub
repository.

- Use a dedicated Google Cloud project, `dofus_dev` and `dofus_prod` base datasets,
  and one single-purpose service account during the solo pilot.
- Use dbt's Core `Latest` release track while hosted BigQuery Fusion support remains
  preview.
- Apply a 1 GB maximum-bytes-billed limit per dbt query and a small BigQuery daily
  query quota.
- Keep dbt Core, dbt-duckdb, the local `profiles.yml`, and DuckDB-based CI during the
  pilot.
- Treat the dbt platform's generated profiles and credentials as environment
  configuration, never as repository files.
- Use only synthetic or contract-approved hosted source data. Do not manually upload
  the private CSV exports to bypass the unresolved source contract.
- Do not schedule a production build until deterministic ingestion and the first real
  models exist.

## Consequences

- Hosted development, connection testing, and future orchestration can be evaluated
  without sacrificing local reproducibility.
- Transformation SQL must continue to remain portable across DuckDB and BigQuery
  until the pilot is accepted as the canonical execution path.
- The project temporarily maintains two analytical targets and must verify model
  parity before retiring either one.
- The free plan requires a service-account JSON key. It must be uploaded directly to
  dbt and never stored in Git; OAuth and workload identity federation require an
  Enterprise-tier dbt plan.
- A later ADR must accept BigQuery as canonical, define the private-data loader, and
  supersede ADR 0001 before dbt Core and DuckDB are removed.
