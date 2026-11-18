# Bob Prompt Register

| Prompt ID | Phase | Title | Issued | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| BOB-P0-01 | P0 | Foundation & scaffolding | 2026-11-17 | Superseded (validation not run) | Skeleton written; no Docker/Node/Git/make; architect rejected the P0 gate. See ADR-013/014. |
| BOB-P0-01-R1 | P0 | Corrective (Docker-based) | n/a | Withdrawn before issue (Docker unavailable) | Never issued; superseded by R2. |
| BOB-P0-01-R2 | P0 | Native toolchain, validation & P0 fixes | 2026-11-17 | Accepted with conditions | Native toolchain; Docker items NOT RUN (deferred to P10). Gate PASSED with conditions 2026-11-18 (eadf6af); conditions C1-C4 closed in BOB-P1-01. |
| BOB-P1-01 | P1 | Database schema, migrations and repositories | 2026-11-18 | Submitted for architect review | P0 carry-over C1-C4 (commit A) and 17-table schema, migration 0001, repositories, integration tests (commit B). Seed generator is BOB-P1-02. |
