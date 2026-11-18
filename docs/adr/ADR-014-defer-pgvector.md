# ADR-014: Defer pgvector to P7

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-11-17 |
| Deciders | Chief Solution Architect, Sponsor |

## Context

pgvector is not installed on the native PostgreSQL 16 for Windows setup (ADR-013), and nothing before the RAG phase needs it.

## Decision

pgvector is deferred to P7. P0 enables no database extension. P1 creates every table except `document_chunks`. P7's first migration enables `vector` and creates `document_chunks`. The P0 migration is therefore an empty baseline, revision `0000`, and the Compose `db` image is `postgres:16` until P7.

## Consequences

- Positive: no extension build or install on Windows before it is needed.
- Negative: the vector path is untested until P7; the P7 migration must run on a server with pgvector available.
- Acceptance check: `\dx` shows only `plpgsql` and `\dt` shows only `alembic_version` after P0.

## Alternatives considered

- Install pgvector on Windows now: extra tooling for no P0 to P6 benefit.
- Use a non-pgvector store: rejected, outside the approved stack.
