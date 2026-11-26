# Project Status

## Phase P3 (part 1): carry-over B1-B3 (BOB-P3-01, Commit A)

- **B1 (decided):** the literal rule 3 stays. An empty idle row (on_hand 0, ADS30 0, SS 0) has IP = ROP = 0 and classifies HIGH (R3) with Q = 0. The earlier architect note ("falls through to LOW") is withdrawn. Tests: `test_risk.py::test_empty_idle_row_is_high_by_rule_3_and_has_zero_reorder_quantity` and `::test_empty_idle_row_metrics_give_zero_reorder_quantity`. P8 creates recommendations only where Q > 0.
- **B2 (decided):** `is_high_demand` is not persisted and the schema stays frozen. P3-02 exposes it as a derived API field from `demand_trend_pct` and the `spike_threshold` in that snapshot's `params_json` (not the current configuration), so old snapshots stay self-consistent.
- **B3 (done):** `make coverage-summary` prints a per-package table (`app/analytics`, `app/services`, `app/repositories`, `app/api`, `app/core`, `data/seed`) from the `.coverage` data of the `make test` run that just finished (`backend/scripts/coverage_summary.py`). It never runs the tests itself. Coverage tables in reports come from the final committed-tree run.
## Phase P2 (part 2): risk classification, flags, roll-up, snapshots, recalculation (BOB-P2-02, Commit B)

**Status: implemented and validated; awaiting architect review.** No new dependencies; pins unchanged. No BP 7 formula, rule order, threshold, Z value or rounding rule was changed. Seed data changed only in the HIGH_DEMAND band (A4, Commit A).

- `app/analytics/` additions: `risk.py` (rules R1 to R6, first match wins, `numpy.select`), `flags.py` (slow, dead, high demand), `rollup.py` (product roll-up, `risk_distribution`, `dashboard_kpis` with warehouse and category filters), `explain.py` (`explain_row`, 12 metrics, risk entry with `rules_checked` and `fired_rule`), `snapshot.py` (`to_snapshot_rows`, 4 dp half-up), `pipeline.py` (`run_analytics` = metrics + context columns + risk + flags).
- `app/services/`: `analytics_service.py` (`RecalculationService.run(triggered_by)`: one transaction with 1 snapshot row, 150 `product_metrics` rows and 1 `audit_log` row, or nothing), `evidence.py` (Table 7.8 check and the evidence report), `errors.py`.
- `app/cli.py`: `python -m app.cli recalc [--triggered-by LABEL] [--report PATH]`; `make recalc`. Exit codes: 0 ok, 1 analytics or data error, 2 bad arguments, 3 database error.
- Startup recalculation (FR-B5): `RECALC_ON_STARTUP` (optional bool). Unset means on when `APP_ENV=local`, off otherwise. A failure is logged with its trace and the app keeps running.
- `GET /api/v1/health/ready` gained an additive `analytics` field: `ok`, `no_snapshot` or `error`. Existing fields are unchanged.

### Results on seed 42 (dev DB, from `docs/evidence/p2_risk_distribution.md`)

| Class | Rows |
| --- | --- |
| STOCKOUT | 3 |
| CRITICAL | 8 |
| HIGH | 4 |
| MEDIUM | 3 |
| OVERSTOCK | 11 |
| LOW | 121 |

Table 7.8: 0 mismatches (29 scenario rows and 121 HEALTHY rows PASS). Recalculation: 191 ms and 195 ms end to end (NFR-03 limit 5000 ms).

### Coverage (final tree, `REQUIRE_TEST_DB=1`)

| Package | Statements | Covered | Percent | Target |
| --- | --- | --- | --- | --- |
| `app/analytics` | 467 | 465 | 99.57 | at least 95 |
| `app/services` | 198 | 189 | 95.45 | at least 90 |
| `app/repositories` | 163 | 162 | 99.39 | n/a |
| `data/seed` | 607 | 603 | 99.34 | at least 85 |

### Traceability additions (BP formula to function to test)

| BP rule | Function | Tests |
| --- | --- | --- |
| 7.4 risk rules R1 to R6, first match wins | `risk.RISK_RULES`, `risk.rule_masks`, `risk.classify_risk` | `tests/unit/analytics/test_risk.py` (30 tests: each rule, each boundary, rule order, null DoC) |
| 7.5 slow, dead, high-demand flags | `flags.is_slow_moving`, `flags.is_dead_stock`, `flags.is_high_demand` | `test_flags.py` (17 tests) |
| 7.4 product roll-up, KPIs (FR-A1) | `rollup.rollup_by_product`, `rollup.dashboard_kpis`, `rollup.risk_distribution` | `test_rollup.py` (17 tests); integration `test_kpis_equal_a_direct_sql_aggregation` |
| FR-A5 explain payload | `explain.explain_row` | `test_explain.py` (10 tests); integration `test_explain_payload_matches_the_stored_metrics_for_five_rows` |
| 5.3 snapshot rows, 4 dp half-up | `snapshot.to_snapshot_rows` | `test_snapshot.py` (14 tests) |
| 7.4 / 7.8 seed classification | `evidence.check_row`, `evidence.SCENARIO_EXPECTATIONS` | integration `test_seed_classification.py` (every row, all six classes) |
| FR-B5 recalculation and audit | `RecalculationService.run`, `recalculate_on_startup` | `test_recalculation.py` (rollback, no data, repeatability, timing, startup, CLI exit codes 0, 1, 2, 3), `tests/unit/test_startup.py` |

### Interpretations and deviations (none silent)

1. **Literal rule 3 on an empty idle row (RESOLVED by architect decision B1 in BOB-P3-01: HIGH is correct, Q = 0, P8 creates recommendations only where Q > 0).** A row with on_hand = 0, ADS30 = 0 and SS = 0 has IP = ROP = 0, so rule 3 (IP <= ROP) makes it HIGH, not LOW as the BP 7.2 note implies. Implemented literally; documented in `test_risk.py::test_literal_rule_3_makes_an_empty_idle_row_with_ip_equal_rop_high`. No such row exists in seed 42.
2. **`DetailedHTTPException`** (`app/core/errors.py`, additive) lets the 503 envelope carry `details`. `/health/ready` with the database down now returns `details {"database": "unavailable", "analytics": "error"}`. Code `INTERNAL_ERROR` and message "Database unavailable" are unchanged.
3. **`RECALC_ON_STARTUP`** is an optional bool; unset defaults from `APP_ENV` (on for `local`). `.env.example` sets `true`; tests set `false`.
4. **`analytics_status`** lives in `app/services` so the API layer does not touch repositories (layering).
5. **`evidence.py`** lives in `app/services` (it reads through the service and renders markdown); **`pipeline.py`** is an extra analytics module that composes the existing steps.
6. **Repositories return `Sequence[RowMapping]`** (plain rows, no DataFrames); the service builds the DataFrames.
7. **`is_high_demand` is not persisted** (restriction). The stored `demand_trend_pct` holds the ratio, and the flag is derived from it.
8. **Table 7.8 expectation mapping:** SLOW_MOVING accepts LOW or OVERSTOCK with the slow flag; HEALTHY means LOW with no persisted flag (seven HEALTHY-class rows have `is_high_demand` true, which is not persisted and does not break the rule).
9. **A3 lesson:** full SHA-256 digests in tracked files trip the secret scan, so only 16-character prefixes appear outside `seed_report.md`.
10. **NOT RUN:** Docker (deferred to P10, ADR-013) and `tree`.
11. **Test-only suppressions:** none. No `type: ignore` and no new `noqa` anywhere (the only `noqa` lines are the pre-existing `E402` in `tests/conftest.py`).


## Phase P2 (part 2): carry-over A1–A4 (BOB-P2-02, Commit A)

- **A1 (accepted):** NaN for `days_of_cover`/`demand_trend` and nullable `Int64` for `projected_stockout_day` stay. At persistence and at every API boundary NaN/`<NA>` maps to SQL `NULL` / JSON `null`. No sentinel numbers.
- **A2 (done):** `projected_stock` and `projected_stockout_day` now ignore arrivals dated on or before t₀ themselves (`t0 < arrival <= t0 + k`), as defence in depth. Test: `test_projection.py::test_arrival_on_or_before_t0_is_ignored`. The P2-01 statement below that `projected_stock` counts every arrival `<= t0 + k` is superseded.
- **A3 (done):** gate outputs must come from a run on the final committed tree; rule added to `docs/TEST_STRATEGY.md`.
- **A4 (done):** the only seed change. HIGH_DEMAND target band narrowed from `L <= DoC <= L+R` to `L+0.25 <= DoC <= L+1.0` at WH-BLR (`data/seed/scenarios.py`; the matching check in `data/seed/report.py`). Reason: under BP 7.4 a HIGH_DEMAND row with DoC in [L, L+R] usually classifies MEDIUM, so the seed could hold no HIGH row. Canonical counts are unchanged (150 levels, 150 policies, 113 incoming, 13,500 sales rows). All scenario checks still PASS. NumPy is still 2.5.5 (K1 record untouched).
  - Overall seed checksum (SHA-256, first 16 hex characters; the full value is in `docs/evidence/seed_report.md`, which the secret scan excludes by exact path): before `6e2e95ea4a97e7f0`, after `e5a3a5fbe8b38581`. The scan pattern matches 40+ character strings, so full digests are not repeated here.
  - HIGH_DEMAND DoC at WH-BLR after the change: SKU-009 21.76 (L=21), SKU-010 5.36 (L=5), SKU-011 10.49 (L=10), SKU-012 14.52 (L=14).

## Phase P2 (part 1): Inventory analytics engine, metric functions (BOB-P2-01)

**Status: implemented and validated; awaiting architect review.** Risk classes, slow/dead flags, snapshots and the recalculation service are BOB-P2-02. No new dependencies; pins unchanged.

- Package `backend/app/analytics/`: `params.py`, `inputs.py`, `metrics.py`, `projection.py`, `numeric.py`, `types.py`, `errors.py`. Pure Pandas/NumPy/stdlib; it imports nothing from `app.repositories`, `app.api`, `app.ai`, `app.db`, `data` or SQLAlchemy, never reads the wall clock and never reads settings (enforced by `tests/unit/test_import_boundaries.py`).
- Stable signatures for P2-02: `build_metric_inputs(products, warehouses, suppliers, policies, levels, incoming, sales, params) -> DataFrame` and `compute_metrics(inputs, params) -> DataFrame`.
- No formula, default, Z value, window or rounding rule was changed from BP 7.1 to 7.3.
- Interpretations (for architect confirmation): `demand_trend` and `days_of_cover` return NaN (not None) in float columns; `projected_stockout_day` is a nullable `Int64` column (`<NA>` for none). `incoming_in_lt` counts arrivals with `t0 < arrival <= t0 + L`; `projected_stock` counts every arrival `<= t0 + k` and relies on `build_metric_inputs` having already dropped arrivals `<= t0`. `lead_time_override_days` of 0 would be treated as an override of 0 (the schema CHECK forbids it).
- `service_level` is converted to float in the input frame; `AnalyticsParams.z_for` rounds to 3 dp then does an exact dictionary lookup (never interpolates).

### Metric definitions implemented (traceability matrix, competency 7)

| BP formula | Function (`app/analytics/`) | Hand-calculated and edge tests (`tests/unit/analytics/`) |
| --- | --- | --- |
| 7.1 parameters, Z table, `z_for`, `to_json` | `params.AnalyticsParams` | `test_params.py`: `test_defaults_match_bp_7_1`, `test_z_for_exact_table_values`, `test_unsupported_service_levels_raise_and_never_interpolate`, `test_to_json_is_serialisable_and_complete` |
| 7.2 ADS_n = sum of last n days / n | `metrics.ads` | `test_metrics.py`: `test_ads_hand_calculated`, `test_ads_only_uses_the_last_n_days_and_keeps_the_index` |
| 7.2 sigma_d, population std (ddof 0) | `metrics.demand_std` | `test_demand_std_is_population_std`, `test_demand_std_uses_ddof_zero_not_ddof_one` |
| 7.2 L = override else supplier | `metrics.lead_time_days` | `test_lead_time_override_beats_supplier_lead_time` |
| 7.2 available = on_hand - committed | `metrics.available` | `test_available_can_be_negative` |
| 7.2 incoming_in_LT (t0 < arrival <= t0+L) | `metrics.incoming_in_lead_time` | `test_incoming_boundaries_around_t0_and_t0_plus_lead_time` |
| 7.2 SS = override else ceil(Z sigma sqrt(L)) | `metrics.safety_stock` | `test_safety_stock_hand_calculated_and_overrides`, `test_safety_stock_override_skips_the_z_lookup`, `test_safety_stock_float_artefact_is_not_rounded_up` |
| 7.2 ROP = ceil(ADS30 L) + SS | `metrics.reorder_point` | `test_reorder_point_hand_calculated` |
| 7.2 DoC = max(0, available) / ADS30 | `metrics.days_of_cover` | `test_days_of_cover_hand_calculated_without_runtime_warnings` |
| 7.2 IP = available + incoming_in_LT | `metrics.inventory_position` | `test_inventory_position` |
| 7.2 Q_raw, Q (MOQ, case pack) | `metrics.reorder_quantity_raw`, `metrics.reorder_quantity` | `test_reorder_quantity_raw_hand_calculated`, `test_reorder_quantity_hand_calculated`, `test_reorder_quantity_is_zero_when_raw_is_not_positive` |
| 7.2 demand trend (14 vs prior 76) | `metrics.demand_trend` | `test_demand_trend_hand_calculated`, `test_demand_trend_custom_windows_and_longer_series` |
| 7.2 inventory value (Decimal 2 dp half-up) | `metrics.inventory_value`, `numeric.money` | `test_inventory_value_is_decimal_two_dp_half_up`, `test_money_is_two_dp_round_half_up` |
| 7.2 all metrics together | `metrics.compute_metrics` | `test_compute_metrics_hand_calculated_rows`, `test_compute_metrics_output_schema_and_dtypes`, `test_compute_metrics_on_the_seed_takes_under_one_second` |
| 7.3 projected stock, stockout day | `projection.projected_stock`, `projection.projected_stockout_day` | `test_projection.py` (17 tests: before/after L, exactly 0, available <= 0 gives day 0, rescue by incoming, ADS30 = 0 gives None) |
| 7.7 safe ceiling (float artefacts) | `numeric.safe_ceil`, `numeric.safe_ceil_array` | `test_numeric.py`: `test_safe_ceil_values`, `test_naive_ceil_really_has_the_artefact`, `test_safe_ceil_array_property_grid` |
| 7.4 input frame, windowing, validation | `inputs.build_metric_inputs` | `test_inputs.py` (23 tests) |
| 7.6 worked example | whole pipeline | `test_worked_example.py::test_worked_example_reproduces_bp_7_6` |
| Property invariants (600 seeded cases) | `compute_metrics` | `test_metrics.py::test_property_*` (3 seeds x 200 rows, plus a scalar oracle) |
| Engineered seed scenarios | `compute_metrics` over the in-memory seed | `test_seed_sanity.py` |
## Phase P1 (part 2): Synthetic data seed generator (BOB-P1-02)

**Status: implemented and validated; awaiting architect review.** Seed 42, t0 2026-09-30. Full outputs are in the BOB-P1-02 report; the generated evidence is `docs/evidence/seed_report.md`.

- Generator: `backend/data/seed/` (`catalog`, `scenarios`, `demand`, `stock`, `report`, `generator`), run with `make seed` (CLI `python -m data.seed.generator`). No new dependencies; pins unchanged.
- **Canonical seed-42 counts** (accepted by the architect, K2): categories 5, suppliers 5, warehouses 3, products 50, inventory_policies 150, inventory_levels 150, sales_daily 13,500, **incoming_stock 113** (3 OPEN covered + 10 OPEN healthy + 96 RECEIVED + 4 CANCELLED).
- `incoming_stock` order-date ranges, measured on the seed-42 data (K4). The sales window starts 2026-07-03 (t0 - 89 days). OPEN covered orders: ordered 2026-09-22 to 2026-09-28 (t0 - 8 to t0 - 2 days). OPEN healthy orders: ordered 2026-09-25 to 2026-09-29 (t0 - 5 to t0 - 1 days). CANCELLED: ordered 2026-08-12 to 2026-09-11. RECEIVED: ordered 2026-06-18 to 2026-09-22. Only RECEIVED orders can be dated before the window start (as early as t0 - 104 days), because their arrival is inside the window and the order date is up to one supplier lead time (at most 21 days) earlier. The claim in the BOB-P1-02 report that a COVERED_BY_INCOMING order_date "can be earlier than t0 - 90" was wrong and is withdrawn (it was in that report, not in this file): COVERED orders are dated t0 - 8 to t0 - 2.
- NumPy guard (K1): `test_numpy_version_matches_the_seed_report` fails if the installed NumPy differs from the version recorded in `docs/evidence/seed_report.md`.
- Not seeded: `metric_snapshots`, `product_metrics`, `replenishment_recommendations`, `approval_decisions`, `executive_reports`, `documents`, `ai_interactions`, `audit_log`, `users`.
- **Currency assumption: all monetary values are INR** (cost bands, prices and revenue).
- **Deviation from BP 5.4 (recorded, not dropped):** the "4 seeded demo users" are **deferred to P3**, which owns password hashing. `users` stays empty until then (BOB-P1-02 7.9).
- Determinism: one `numpy.random.default_rng(seed)`; no `random`, `uuid`, wall clock or hash-dependent ordering in the data path. The RNG stream is only guaranteed for the pinned NumPy (2.5.5), so a NumPy upgrade can change the checksums and the report records the NumPy version.
- Checksums use natural keys (SKU, warehouse code) rather than surrogate ids, so they match between the generated data and the data read back from the database, across re-seeds.
- Scenario formulas in `data/seed/scenarios.py` are generator **design targets** only. They are not business logic, `app/` never imports `data/`, and P2 implements the real formulas independently (enforced by `tests/unit/test_import_boundaries.py`).
- Where a random draw would miss a band, the value is fitted back deterministically (clamping `available`, scaling the last 14 or 30 days of demand). There are no RNG retry loops.
- `secret-scan` excludes the exact path `docs/evidence/seed_report.md`: it lists SHA-256 checksums (64 hex characters), which match the long-string pattern but are not secrets.
- `mypy` now covers `app` and `data/seed` (strict), and pytest coverage covers `app` and `data/seed`.
- `REQUIRE_TEST_DB` (Q4): `make test` defaults to `1` (unreachable test DB fails); see `docs/TEST_STRATEGY.md`.

## Phase P1 (part 1): Database schema, migrations and repositories (BOB-P1-01)

**Status: implemented; finally accepted after the E1 re-run evidence in BOB-P1-02 (commit A).**

- Alembic head: `0001_core_schema` (17 tables plus `alembic_version`). `document_chunks` and the `vector` extension are absent (ADR-014).
- Databases: `smartstock` (dev) and `smartstock_test` (integration tests), both owned by `smartstock`.
- No new dependencies; pins unchanged.

### BP §5 clarifications

These are clarifications from BP §9.2, not design changes (recorded as required by BOB-P1-01 §7.3):

- `documents.status` (`UPLOADED`/`INDEXED`/`FAILED`, default `UPLOADED`).
- `documents.injection_warning` (boolean, default false).

### Interpretations made in BOB-P1-01 (for architect confirmation)

- Columns are NOT NULL unless §7.3 says `null`/`null allowed`. This was applied to columns whose nullability the table did not state (for example `product_metrics.*`, `inventory_levels.as_of`).
- `approval_decisions.decision` and similar columns with a CHECK but no stated default are NOT NULL with no default.
- `ai_interactions.validation_status` and `feature` are NOT NULL.
- `audit_log` has an index on `occurred_at` and one on `(entity_type, entity_id)` (spec: `index on (occurred_at), (entity_type, entity_id)`), plus `user_id` (every FK is indexed).
- `sales_daily`: besides the PK `(product_id, warehouse_id, sale_date)` and the required `sale_date` index, `warehouse_id` has its own index (FK rule).
- `UNIQUE` constraint names follow the requested convention (`uq_<table>_<first column>`), so `UNIQUE(product_id, warehouse_id)` is named `uq_inventory_levels_product_id`.
- `AiInteractionRepository.set_feedback` returns `True`/`False` (row found or not) and flushes; it does not commit.
- Every table is mapped without ORM `relationship()` objects (thin layer; joins are explicit queries).

## Phase P0: Foundation & scaffolding (BOB-P0-01 / BOB-P0-01-R2)

**Status: P0 gate passed on the native toolchain, except the items below that are explicitly NOT RUN.**

- Deferred to P10: Docker validation (`docker compose up --build`, image builds). The Dockerfiles and `docker-compose.yml` are present and updated per ADR-013, but NOT RUN: deferred to P10 (ADR-013).
- The real "PostgreSQL service stopped" check was NOT RUN: the shell is not elevated, so `Stop-Service` was denied. The DB-down path was verified instead by starting the backend with `POSTGRES_PORT=59999` (unreachable); see the R2 report.

### Tool versions (host)

| Tool | Version |
| --- | --- |
| Git | 2.56.1.windows.1 |
| Node.js | v26.13.1 (LTS codename "Lithium") |
| npm | 11.20.0 |
| Python (venv) | 3.12.0 (`py -3.12`) |
| GNU Make | 3.81 (GnuWin32; also runs from Git Bash) |
| PostgreSQL | 16.16 (service `postgresql-x64-16`) |

### Pinned versions

Python: direct pins in `backend/pyproject.toml`; full transitive lock in `backend/requirements.lock` (`pip freeze --exclude-editable`, Python 3.12.0). Python `>=3.12,<3.13`.

| Package | Version |
| --- | --- |
| fastapi | 0.163.1 |
| uvicorn[standard] | 0.54.0 |
| pydantic | 2.14.3 |
| pydantic-settings | 2.16.3 |
| sqlalchemy | 2.1.9 |
| alembic | 1.20.1 |
| psycopg[binary] | 3.3.9 |
| pandas | 3.1.1 |
| numpy | 2.5.5 |
| pytest (dev) | 9.2.0 |
| pytest-cov (dev) | 7.1.0 |
| httpx (dev) | 0.28.1 |
| ruff (dev) | 0.17.5 |
| mypy (dev) | 2.4.1 |
| setuptools (build) | 80.9.0 |

Node: exact versions in `frontend/package.json`; full tree in `frontend/package-lock.json`. The versions below are those resolved in the lock.

| Package | Version |
| --- | --- |
| react, react-dom | 18.3.1 |
| @mui/material, @mui/icons-material | 7.3.11 |
| @emotion/react | 11.14.0 |
| @emotion/styled | 11.14.1 |
| recharts | 2.15.4 |
| axios | 1.21.1 |
| react-router-dom | 6.30.6 |
| vite | 5.4.21 |
| @vitejs/plugin-react | 4.7.0 |
| typescript | 5.9.3 |
| vitest | 2.1.9 |
| @testing-library/react | 16.3.3 |
| @testing-library/dom | 10.4.2 |
| @testing-library/jest-dom | 6.10.0 |
| jsdom | 25.0.1 |
| eslint, @eslint/js | 9.39.5 |
| typescript-eslint | 8.73.0 |
| eslint-plugin-react-hooks | 5.2.0 |
| globals | 15.15.0 |
| prettier | 3.10.1 |
| @types/react | 18.3.31 |
| @types/react-dom | 18.3.7 |

Pin changes: none. Every pin installed and passed lint, typecheck and tests unchanged.

Base images (Docker, not run): `postgres:16`, `python:3.12-slim`, `node:lts-slim` (tags, not digests).

### Known items

- `npm` warns that `esbuild@0.21.5` has a postinstall script not covered by `allowScripts`; the dev server and tests work.

### C3: npm audit summary (BOB-P1-01, 2026-11-18; nothing upgraded)

The P0 report quoted 17 vulnerabilities. `npm audit` now reports **8 (2 critical, 1 high, 5 moderate)**; the advisory database changed and the lock file did not. `npm audit --omit=dev` reports **2 moderate** (both runtime). Architect decides by P4.

| Package | Severity | Runtime or dev-only | Vulnerable range | Fix offered by npm (all semver-major) | Advisories |
| --- | --- | --- | --- | --- | --- |
| vitest | critical | dev-only | <=4.1.10 | vitest@5.1.1 | GHSA-5xrq-8626-4rwp, GHSA-82fw-gwwq-j7x9 |
| tinypool | critical | dev-only | <=2.1.1 | vitest@5.1.1 | GHSA-5gmw-xhrv-c9v3, GHSA-85c8-ppgw-ccpr |
| vite | high | dev-only | <=6.4.3 | vite@8.3.8 | 8 advisories, e.g. GHSA-4w7w-66w2-5vf9 (path traversal in optimized deps `.map` handling) |
| esbuild | moderate | dev-only | <=0.24.2 | vite@8.3.8 | GHSA-67mh-4wv8-2f99 (dev server accepts requests from any website) |
| @vitest/mocker | moderate | dev-only | <=4.1.11 | vitest@5.1.1 | GHSA-82fw-gwwq-j7x9, GHSA-qxg6-89mg-rqv8 |
| vite-node | moderate | dev-only | <=2.2.0-beta.2 | vitest@5.1.1 | via vitest/vite |
| react-router | moderate | runtime | 6.0.0 - 7.17.0 | react-router-dom@7.18.6 | GHSA-wrjc-x8rr-h8h6 (open redirect), GHSA-337j-9hxr-rhxg (constructor injection in SSR hydration) |
| react-router-dom | moderate | runtime | 6.0.0-alpha.0 - 7.17.0 | react-router-dom@7.18.6 | via react-router |

Notes: all the critical and high findings are in the test/dev toolchain (Vitest, Vite) and affect developer machines running dev servers. The two runtime findings are in React Router. The SSR hydration advisory does not apply (client-side SPA only). The open-redirect advisory concerns `<Link>`/`useNavigate` with untrusted URLs. Every fix is a major-version bump (Vitest 5, Vite 8, React Router 7), so none was applied.

### C4: Starlette/httpx deprecation warning in pytest

Full text:

```
.venv\Lib\site-packages\fastapi\testclient.py:1
  ...\backend\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa
```

Source: `starlette/testclient.py` (Starlette 1.10.0) tries `import httpx2` first and, if missing, falls back to `httpx` and emits this warning. `fastapi.testclient` re-exports Starlette's `TestClient`, so the warning fires on import. The only real fix is to add `httpx2` as a dev dependency (a new package, outside the pinned set), so it is **not fixed** and is recorded here. Suppressing it with a `filterwarnings` entry was not done, to avoid hiding future deprecations. Proposal for the architect: swap `httpx==0.28.1` for `httpx2` in the dev extras once a version is approved.

## P3-01 status (2026-11-24)

- Auth (bcrypt + PyJWT, ADR-015), RBAC (ROLE_MATRIX = BP §10.2), audit-derived lockout, 1 MB request limit, Page[T],
  /auth/login, /auth/me, /admin/audit-log, /admin/ai-interactions, make seed-users, make coverage-summary.
- New runtime deps: bcrypt, PyJWT. Known: StarletteDeprecationWarning (httpx -> httpx2) recorded, not fixed.
- Development agent changed to Claude Code from P3-01 closure (ADR-016).

### P3-01 final gates (2026-11-25, clean tree at 0c461d0)

| Gate | Result |
| --- | --- |
| `make lint` | PASSED (ruff check: all checks passed; ruff format: 122 files formatted; eslint clean; secret scan passed) |
| `make typecheck` | PASSED (mypy strict: no issues in 77 source files; `tsc --noEmit` clean) |
| `make test` | PASSED (backend 705 passed, 1 warning (StarletteDeprecationWarning, C4); total coverage 99%; frontend 4 passed) |
| AC-3.7 demo | Temporary unauthenticated `GET /api/v1/debug-open`: `test_route_protection.py` 7 failed / 4 passed, naming the route. Route removed: 11 passed |
| Pre-commit secret scan | ALLOWED with no findings after `DUMMY_HASH` became generated at import (no hash literal in source) |

`make coverage-summary`:

| Package | Statements | Missed | Covered % |
| --- | --- | --- | --- |
| app/analytics | 467 | 2 | 99.57 |
| app/services | 350 | 10 | 97.14 |
| app/repositories | 205 | 2 | 99.02 |
| app/api | 110 | 0 | 100.00 |
| app/core | 242 | 0 | 100.00 |
| data/seed | 607 | 4 | 99.34 |

## P3-02a status (2026-11-25)

- Endpoints #5-#13 (all `GET`, capability `view_inventory` via `require_capability`): `/reference/categories`, `/reference/warehouses`, `/reference/suppliers` (no `contact_email`), `/products` (paged roll-up, filters, sorting, `q` with escaped wildcards), `/products/{id}`, `/products/{id}/sales`, `/dashboard/summary`, `/dashboard/sales-trend`, `/dashboard/risk-distribution`.
- Every number comes from `rollup_by_product`, `dashboard_kpis` or `risk_distribution` over the latest snapshot, or from raw `sales_daily` rows. No new calculations. `is_high_demand` reuses `analytics.flags.is_high_demand` with the snapshot's own `params_json["spike_threshold"]` (`app/services/snapshot_context.py`).
- Snapshot-derived responses carry `snapshot: {snapshot_id, calculated_at, data_as_of_date, verified: true}`. Money is a 2-dp decimal string; ADS, DoC and trend are 4-dp numbers; null stays null.
- Errors: unknown product or filter id -> 404 `NOT_FOUND`; no snapshot -> 409 `CONFLICT` ("No analytics snapshot available. Run a recalculation."); bad parameters -> 422. Series t0 = latest snapshot `data_as_of_date`, else `max(sale_date)`; with no sales at all -> 409 "No sales data available." (decision made here: there is no date to anchor the series).
- Canonical seed-42 values reproduced and cross-checked against direct SQL: total_products 50, total_units 73484, inventory_value "89944367.37", low_stock 7, stockout_risk 15, slow_moving 11; rows LOW 121, OVERSTOCK 11, CRITICAL 8, HIGH 4, MEDIUM 3, STOCKOUT 3.
- Additive fields beyond BP 6.3: `warehouse_code` on `ProductMetricOut` (the detail rows are sorted by it). `DashboardSummaryOut` carries `snapshot_id`/`calculated_at` inside `snapshot`, as the prompt specifies.
- NFR-01 medians (5 warm requests, in-process client, working tree before commit): categories 6.5 ms, warehouses 8.4 ms, suppliers 8.4 ms, products 31.6 ms, product detail 30.0 ms, product sales 10.9 ms, summary 25.2 ms, sales-trend 44.1 ms, risk-distribution 30.7 ms. All under 500 ms. Final-tree values are in the P3-02a report.
- Tests (working tree before commit): backend 783 passed; new modules: `app/api/v1/reference.py`, `products.py`, `dashboard.py`, `app/api/errors.py`, `app/services/snapshot_context.py` 100%; `inventory_service.py` 99%; `dashboard_service.py` 97%. `test_route_protection` passes with the nine new routes protected automatically.

## P3-02b status (2026-11-25)

- Endpoints #14-#20: `GET /analytics/metrics` (row-level page of any snapshot, filters, sort),
  `GET /analytics/metrics/{id}/explain?warehouse_id=`, `POST /analytics/recalculate` (ADMIN,
  201), `GET /analytics/snapshots` (newest first, per-class counts from one grouped query, no
  `params_json`), `GET /risk/stockout`, `GET /risk/{id}?warehouse_id=`, `GET /risk/slow-moving`.
  All need `view_inventory`; #16 also needs `recalculate_analytics`.
- Exact explanations (FR-B6, `app/services/explain_service.py`): `recompute_rows` reloads the raw
  data as of the snapshot's `data_as_of_date` through the recalculation's own loader
  (`analytics_service.load_metric_inputs`, now shared, with optional product and warehouse
  filters), rebuilds `AnalyticsParams` from the snapshot's `params_json` (every field, `z_table`
  included), runs the pipeline for the requested rows only and compares 12 fields on the storage
  scale (`to_snapshot_rows`). Any difference raises 409 `CONFLICT` with `details.fields` (names
  only). All 150 rows of the seed-42 snapshot recompute to their stored values (test).
- `GET /risk/stockout` also uses the verified recompute (for the rows on the page) to serve
  `projected_stockout_day`, which is not stored. So a stale snapshot gives 409 there too.
- Recalculation lock: `RecalculationService.run` takes `pg_try_advisory_xact_lock(0x53534149)`
  (SQLAlchemy `func`) in its own transaction, for every caller (API, CLI, startup). A refusal
  rolls back, writes `ANALYTICS_RECALC_REJECTED` (`reason: lock_held`) and raises
  `RecalculationLockedError` (API 409 "A recalculation is already running."). The audit rows
  carry `user_id`, `request_id` and `ip_address` from the API; the CLI and startup pass none.
  `triggered_by` is `api:<username>` with characters outside `[a-z0-9_-]` mapped to `-`.
- API recalculation errors: no sales -> 409 "No sales data available."; analytics failure ->
  500 "Recalculation failed." (code logged); any other failure -> 500 `INTERNAL_ERROR` via the
  generic handler. Each rolls back: no snapshot, no `ANALYTICS_RECALCULATED` row.
- OpenAPI baseline: `make openapi` writes `docs/api/openapi-v1.json` (sorted keys, 2-space indent,
  trailing newline); `tests/unit/test_openapi_contract.py` fails on any difference.
- Interpretations (none silent): `#20` items add `is_dead_stock` (the sort key; `ads_90` was
  already in `ProductMetricOut`); `#19` adds `lead_time_days` and `is_high_demand` to the
  `ProductMetricOut` fields; rule ids are `"R1"`..`"R6"` and the class key is `class` as the
  prompt names it; `/risk/{id}` lists every OPEN arrival after t0 in `open_incoming` (the
  projection itself only counts arrivals up to t0 + k).

## P4-01 status (2026-11-26)

- Dependencies (commit 1, approved in BOB-P4-01 7.1; versions pinned exactly):

  | Package | Before | After | Why |
  | --- | --- | --- | --- |
  | react-router-dom | 6.30.6 | removed | v7 merges it into `react-router` |
  | react-router | (via -dom) | 7.18.7 | runtime advisories; v8 needs React 19, so v7 (supports React 18) |
  | vite | 5.4.21 | 8.3.8 | high (vite, esbuild) |
  | @vitejs/plugin-react | 4.7.0 | 6.3.0 | peer of Vite 8 |
  | vitest | 2.1.9 | 5.1.2 | critical (vitest, tinypool), moderate (@vitest/mocker, vite-node) |
  | @vitest/coverage-v8 | – | 5.1.2 | new dev dep (approved): `vitest --coverage` |
  | openapi-typescript | – | 7.13.0 | new dev dep (approved): `npm run gen:api` |

  `npm audit` before: **8 vulnerabilities (2 critical, 1 high, 5 moderate)**; after: **found 0
  vulnerabilities**. Nothing left to document. `npm audit fix --force` was not used. This closes
  C3 (the BOB-P1-01 audit note).
- Backend (API v1.1, additive): `GET /auth/me` returns `capabilities`, the role's BP 10.2 row,
  sorted (`app.core.rbac.capabilities_for`). Integration test pins each of the 4 rows. No other
  backend change.
- Typed client: `npm run gen:api` writes `frontend/src/api/schema.d.ts` from
  `docs/api/openapi-v1.json` (committed). `src/api/schema.fresh.test.ts` regenerates it and fails
  if the committed file differs; `src/api/types.ts` names the shapes the UI uses.
- Auth (ADR-006): `AuthProvider` holds `{token, user, capabilities, expiresAt}` in React state only
  (test: no localStorage, sessionStorage or cookie writes); a refresh means signing in again.
  Automatic sign-out at `expiresAt` ("Your session expired. Please sign in again.").
- API client: Bearer token and a UUID `X-Request-ID` on every request; failures become
  `ApiError {status, code, message, requestId, details, retryAfter}` from the BP 6.1 envelope;
  401 (except login) signs out ("Please sign in again."); 403 shows "You don't have permission
  for this action."; network and 5xx show "Service unavailable. Try again later." with the
  reference. An error boundary shows a safe fallback.
- Navigation is a typed config (`src/layout/navConfig.ts`) filtered by `capabilities`; the UI never
  checks a role name (the role is only displayed). Now: Dashboard (placeholder, `view_inventory`)
  and Admin > Audit log (`view_governance`). Routes `/login`, `/`, `/dashboard`,
  `/admin/audit-log`, `*`.
- Components: `VerifiedDataPanel`, `AiNarrativePanel`, `KpiTile`, `RiskBadge`, `DataTable`,
  `ErrorState`, `ApiErrorSnackbar`, `ErrorBoundary`; formatters in `src/lib/format.ts` (money from
  the decimal string, no float). Risk colours and their AA contrast are in `src/theme/theme.ts`
  and checked by `theme.test.ts`.
- The P0 Home page and its test are removed; the health check survives as a small
  "Backend: ok/unavailable" indicator at the foot of the navigation drawer.
- Known limitation: the backend's CORS setup exposes only `X-Request-ID`, so a browser on another
  origin cannot read `Retry-After`; the 429 message then says "Try again later." instead of the
  minutes. Exposing `Retry-After` is a one-line CORS change that needs an architect decision
  (BOB-P4-01 kept CORS unchanged).

## P4-02 status (2026-11-26)

- E1: the backend CORS setup exposes `Retry-After` next to `X-Request-ID`
  (`backend/app/main.py`; test `test_cors_exposes_request_id_and_retry_after`), so the login page
  shows the lockout minutes in the browser. CORS config only: `make openapi` shows no diff.
- E2: route-level code splitting (`React.lazy` + `Suspense` with a skeleton fallback) for the
  Dashboard, Admin > Audit log and NotFound pages; the shell and the login page stay in the main
  chunk. `npm run build` before: one chunk `index` 553.66 kB (gzip 177.30 kB) with the
  "chunks are larger than 500 kB" warning. After E2 alone: largest chunk 437.81 kB, no warning.
  With the dashboard (Recharts lives in the Dashboard chunk): largest chunk `Dashboard`
  431.97 kB (gzip 115.80 kB), main `index` 131.66 kB, no warning. No build-config change.
- Dashboard (`frontend/src/pages/Dashboard.tsx`, `src/pages/dashboard/`): every number comes from
  the API in a verified panel. Header snapshot line "Verified · calculated <time zone> · data as
  of <date>"; six KPI tiles with BP 7.4 definitions as tooltips; 30/60/90-day units trend with a
  labelled "Sum of the series shown" (units, and revenue summed exactly in paise, no floats) and a
  screen-reader table; risk distribution (Locations = rows, Products = rolled-up) with theme risk
  colours and a "CLASS: count" label on every bar; top 10 from `/risk/stockout?page_size=10`;
  filters in `?warehouse_id=&category_id=` (validated against `/reference/*`; an invalid id falls
  back to All with a notice; the sections wait for validation, so no request uses an unchecked id).
- Recalculate (`recalculate_analytics` only): confirm dialog, `POST /analytics/recalculate`,
  snackbar "Snapshot <id> created (N rows, <ms> ms)", every section reloads; 409 lock shows
  "A recalculation is already running."; disabled while running; other errors use the error
  snackbar (a 403 is left to the P4-01 interceptor).
- States: a 409 without `details.fields` from summary or distribution is "no snapshot" (page-level
  empty state; admin "Run first calculation", others "Ask an administrator to run a
  calculation."); a 409 with `details.fields` from `/risk/stockout` is "stale" (section notice, admin
  Recalculate action); any other error is an inline `ErrorState` with the reference and Retry.
- `src/hooks/useApi.ts`: `{data, error, loading, reload}`, `AbortController` per request (aborted
  on new parameters, reload and unmount); no new dependency.
- Interpretations (none silent): the KPI tiles sit 3 x 2 at 1280 px (six across from 1536 px),
  because six tiles at 1280 px leave about 116 px for "₹8,99,44,367.37"; the sales trend is not
  snapshot-derived, so its badge reads "Verified · sales to <end date>" instead of a calculated
  time; the trend axis labels are "Date" and "Units sold"; `RISK_CLASSES` order fixed to the
  backend order (D-P4-004); the "Run first calculation" and stale-notice buttons unmount once the
  recalculation succeeds and the page reloads, so their success snackbar is replaced by the
  reloaded dashboard (the header button keeps its snackbar).

## API change log

Every change to `docs/api/openapi-v1.json` is listed here (newest first). Export with
`make openapi`; the contract test fails until the file matches the code.

| Date | Version | Change | Prompt |
| --- | --- | --- | --- |
| 2026-11-26 | v1.1 – additive: `capabilities` on `GET /auth/me` (P4-01) | `MeResponse` gains `capabilities: string[]` (the role's BP 10.2 capability keys, sorted). No field removed or renamed. | BOB-P4-01 |
| 2026-11-25 | v1 baseline – P3 complete | First export: endpoints #1-#20 and #33 (health, auth, admin, reference, products, dashboard, analytics, risk). | BOB-P3-02b |

### P3-02b final gates (2026-11-25, clean tree at 2d5aa58)

| Gate | Result |
| --- | --- |
| `make lint` | PASSED (ruff check: all checks passed; ruff format: 148 files already formatted; eslint clean; secret scan passed) |
| `make typecheck` | PASSED (mypy strict: no issues in 92 source files; `tsc --noEmit` clean) |
| `make test` | PASSED (backend 843 passed, 1 warning (StarletteDeprecationWarning, C4); total coverage 99%; frontend 4 passed) |
| `make openapi && git status --short` | No change (the committed baseline equals the export) |
| Contract demo | Added an undeclared field to `SnapshotOut` without `make openapi`: `test_openapi_document_equals_the_committed_baseline` FAILED with "API contract changed: ...". Reverted: 4 passed |
| Pre-commit secret scan | ALLOWED, no secrets found |

NFR-01 medians (5 warm requests, in-process client, committed tree): metrics 16.0 ms, explain 41.6 ms, snapshots 6.6 ms, risk/stockout 61.2 ms, risk detail 40.9 ms, risk/slow-moving 15.8 ms (P3-02a endpoints 4.0-28.1 ms). NFR-03: `POST /analytics/recalculate` median of 3 runs 118.9 ms.

`make coverage-summary`:

| Package | Statements | Missed | Covered % |
| --- | --- | --- | --- |
| app/analytics | 467 | 2 | 99.57 |
| app/services | 792 | 13 | 98.36 |
| app/repositories | 268 | 2 | 99.25 |
| app/api | 264 | 0 | 100.00 |
| app/core | 242 | 0 | 100.00 |
| data/seed | 607 | 4 | 99.34 |

New modules: `api/v1/analytics.py`, `api/v1/risk.py`, `api/errors.py`, `schemas/analytics.py`, `schemas/risk.py`, `services/risk_service.py` 100%; `explain_service.py` 98%; `snapshot_context.py` 98%; `analytics_service.py` 96%; `cli.py` 98%.

### P4-01 final gates (2026-11-26, clean tree at fd520aa)

| Gate | Result |
| --- | --- |
| `git status --short` | empty |
| `npm audit` (frontend) | found 0 vulnerabilities (before P4-01: 8 = 2 critical, 1 high, 5 moderate) |
| `make lint` | ruff: All checks passed, 148 files already formatted; eslint clean; Secret scan passed |
| `make typecheck` | mypy: no issues found in 92 source files; tsc clean |
| `make test` | backend 847 passed, 1 warning (known Starlette deprecation, C4), TOTAL 99%; frontend 12 files, 138 tests passed; exit 0 |
| `npx vitest run --coverage` | lines 98.87% (351/355), statements 97.76%, branches 94.87%, functions 95.52% (threshold: lines 80%) |
| `make openapi && git status --short` | no change |

| Package | Statements | Missed | Covered % |
| --- | --- | --- | --- |
| app/analytics | 467 | 2 | 99.57 |
| app/services | 792 | 13 | 98.36 |
| app/repositories | 268 | 2 | 99.25 |
| app/api | 265 | 0 | 100.00 |
| app/core | 244 | 0 | 100.00 |
| data/seed | 607 | 4 | 99.34 |

Browser checks (headless Edge at 1280 x 800 driven over the DevTools protocol; committed code;
backend on port 8001 and Vite on 5173 with `VITE_API_BASE_URL` overridden for that process only,
because port 8000 was still held by the stale 18 Nov server): 17/17 passed. Signed-out `/` goes
to `/login`; a wrong password shows "Invalid username or password."; admin lands on the dashboard
with Admin > Audit log in the menu, name and role in the app bar; no localStorage,
sessionStorage or cookie; no horizontal scroll at 1280 px; the audit log loads rows, shows the
server total, expands a row to JSON and loads page 2; a refresh returns to `/login`; analyst has
no Audit log menu item; typing `/admin/audit-log` as analyst shows the 403 page.
Screenshots: `docs/evidence/p4-login.png`, `p4-shell-admin.png`, `p4-audit-log.png`,
`p4-forbidden-analyst.png`.

### P4-02 final gates (2026-11-26, clean tree at 2ba24f9)

| Gate | Result |
| --- | --- |
| `git status --short` | empty |
| `npm audit` | found 0 vulnerabilities |
| `npm run build` | no chunk warning; largest `Dashboard` 432.15 kB (gzip 115.86 kB), `TextField` 283.44 kB, `index` 131.66 kB (before E2: one 553.66 kB chunk with the warning) |
| `make lint` | ruff: All checks passed, 148 files already formatted; eslint clean; Secret scan passed |
| `make typecheck` | mypy: no issues found in 92 source files; tsc clean |
| `make test` | backend 848 passed, 1 warning (C4), TOTAL 99%; frontend 14 files, 178 tests passed; exit 0 |
| `npx vitest run --coverage` | lines 98.36% (601/611), statements 97.82%, branches 94.82%, functions 95.37% (threshold 80%) |
| `make openapi && git status --short` | no change (E1 is CORS only) |

| Package | Statements | Missed | Covered % |
| --- | --- | --- | --- |
| app/analytics | 467 | 2 | 99.57 |
| app/services | 792 | 13 | 98.36 |
| app/repositories | 268 | 2 | 99.25 |
| app/api | 265 | 0 | 100.00 |
| app/core | 244 | 0 | 100.00 |
| data/seed | 607 | 4 | 99.34 |

Browser checks (headless Edge driven over the DevTools protocol, committed code; port 8000 was
still held by the stale 18 Nov server, so the backend ran on 8001 and Vite on 5173 with
`VITE_API_BASE_URL` overridden for that process only, as BOB-P4-02 section 16 allows): 23/23 passed.

- Admin, unfiltered: tiles 50 / 73,484 / ₹8,99,44,367.37 / 7 / 15 / 11; distribution (Locations)
  3/8/4/3/11/121; top 10 starts SKU-001/002/003 STOCKOUT, 10 rows; four Verified badges; snapshot
  line "Verified · calculated 26 Nov 2026, 19:52 IST · data as of 30 Sept 2026"; no horizontal
  scroll at 1280 px or 960 px.
- WH-MUM: URL `?warehouse_id=10`; tiles 50 / 25,741 / ₹2,89,42,359.19 / 3 / 8 / 3; after a reload
  and sign-in the same URL and values return.
- Trend 30/60/90 refetches (30 / 60 / 90 rows; sums change); Products mode sums to 50 products.
- Recalculate: "Snapshot 16 created (150 rows, 575 ms)"; analyst has no Recalculate button.
- Empty state: shown by intercepting `GET /dashboard/summary` in the browser (DevTools Fetch domain)
  and answering the API's no-snapshot 409; no database was changed. Admin sees "Run first
  calculation"; analyst sees "Ask an administrator to run a calculation."
- Lockout: six failed sign-ins for a non-existent username (no real account locked) show
  "Too many failed attempts. Try again in 15 minutes." (`Retry-After` now readable, E1).
- Load time, sign-in click to all four sections loaded: 2316, 849, 839, 952, 1026 ms; median
  952 ms. The first sample is the first visit, when the dev server serves the lazy dashboard
  modules cold.
- Screenshots: `docs/evidence/p4-dashboard-admin.png`, `p4-dashboard-filtered-wh-mum.png`,
  `p4-dashboard-analyst.png`, `p4-dashboard-empty-state.png`, `p4-lockout-minutes.png`.
