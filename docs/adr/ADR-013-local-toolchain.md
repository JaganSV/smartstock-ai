# ADR-013: Local native toolchain (amended)

| Field | Value |
| --- | --- |
| Status | Accepted |
| Date | 2026-11-17 |
| Deciders | Chief Solution Architect, Sponsor |

## Context

Docker is not available on the developer machine, so BOB-P0-01 could not be validated (no Docker, Node, Git or make, Python 3.13 instead of 3.12, no PyPI access). The architect rejected the P0 gate as not passed.

## Decision

The developer machine runs Python 3.12, Node LTS, Git, GNU Make (from Git Bash) and native PostgreSQL 16 for Windows. Tests and lint run on the host. `Dockerfile`s and `docker-compose.yml` stay in the repo (the "Docker-ready" requirement) but are not run until P10, on a Docker-capable machine. Python stays `>=3.12,<3.13`. Transitive Python dependencies are locked with `pip freeze` into `backend/requirements.lock`.

## Consequences

- Positive: P0 to P9 can be built and validated on the host without Docker.
- Negative: the Docker path is unvalidated until P10, so container-specific defects may surface late.
- Positive: `backend/requirements.lock` and `frontend/package-lock.json` make builds reproducible.
- Constraint: no uv, Poetry, pip-tools, pnpm or yarn.

## Alternatives considered

- Wait for a Docker-capable machine: blocks all phases.
- Remove the Docker files: loses the Docker-ready requirement.
