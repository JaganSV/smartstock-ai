# Bob Prompt Register

| Prompt ID | Phase | Title | Issued | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| BOB-P0-01 | P0 | Foundation & scaffolding | 2026-11-17 | Superseded (validation not run) | Skeleton written; no Docker/Node/Git/make; architect rejected the P0 gate. See ADR-013/014. |
| BOB-P0-01-R1 | P0 | Corrective (Docker-based) | n/a | Withdrawn before issue (Docker unavailable) | Never issued; superseded by R2. |
| BOB-P0-01-R2 | P0 | Native toolchain, validation & P0 fixes | 2026-11-17 | Accepted with conditions | Native toolchain; Docker items NOT RUN (deferred to P10). Gate PASSED with conditions 2026-11-18 (eadf6af); conditions C1-C4 closed in BOB-P1-01. |
| BOB-P1-01 | P1 | Database schema, migrations and repositories | 2026-11-18 | Provisionally accepted 2026-11-19; final acceptance on E1 re-run evidence (BOB-P1-02 commit A) | P0 carry-over C1-C4 (commit A) and 17-table schema, migration 0001, repositories, integration tests (commit B). Seed generator is BOB-P1-02. |
| BOB-P1-02 | P1 | Synthetic data seed generator | 2026-11-19 | Accepted (P1 gate PASSED 2026-11-19, a272af5) | Commit A (7573280): P1-01 closure (E1 evidence, Q3 identity rule, Q4 `REQUIRE_TEST_DB`). Commit B: deterministic seed generator, coverage report, tests. `users` seeding deferred to P3. |
| BOB-P2-01 | P2 | Inventory analytics engine, part 1 (metric functions) | 2026-11-19 | Submitted for architect review | Commit A: P1 carry-over K1-K4. Commit B: `app/analytics` (params, inputs, metrics, projection, numeric), traceability matrix, 600-case property grid. Risk classes and snapshots are BOB-P2-02. |
| BOB-P2-02 | P2 | Inventory analytics engine, part 2 (risk, flags, roll-up, snapshots, recalculation) | 2026-11-20 | Submitted for architect review | Commit A (4fe37b6): carry-over A1-A4 (A4 is the HIGH_DEMAND seed band). Commit B: risk rules R1-R6, flags, roll-up and KPIs, explain payloads, snapshot rows, RecalculationService, python -m app.cli recalc, startup hook, additive nalytics health field, Table 7.8 evidence. Docker NOT RUN (ADR-013). |
