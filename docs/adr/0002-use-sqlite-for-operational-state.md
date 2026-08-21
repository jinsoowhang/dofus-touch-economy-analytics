# ADR 0002: Use SQLite for operational application state

- Status: Accepted
- Date: 2026-08-20

## Context

The local website records mutable price observations, import results, identity decisions, and invalidations. These are transactional operational concerns, while the existing DuckDB and dbt stack is designed for reproducible analytical loading and transformation.

Writing browser requests directly to DuckDB would mix ownership, couple website availability to analytics, and make transactional history management less explicit.

## Decision

Use an ignored local SQLite database as the FastAPI application's operational store. Manage its schema with Alembic and access it through synchronous SQLAlchemy repositories and services.

Keep DuckDB and dbt as a separate downstream analytical system. A later milestone will read immutable operational extracts into DuckDB; FastAPI performs no request-time DuckDB writes.

## Consequences

- SQLite and DuckDB are two ignored databases with distinct owners and lifecycles.
- Mutable application commands remain transactional and local.
- Price observations are append-only and incorrect records are invalidated rather than edited or deleted.
- Operational schema changes require reviewed Alembic migrations.
- The future analytical bridge must preserve stable identifiers, timestamps, market context, provenance, and invalidation state.
- Public deployment remains deferred until authentication, authorization, CSRF protection, HTTPS, managed secrets, and a production database are designed.
