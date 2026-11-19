# SmartStock AI — Seed Report

Synthetic data — fictional entities only.

- Seed: `42`
- data_as_of_date (t0): `2026-09-30`
- Sales window: `2026-07-03` to `2026-09-30` (90 days)
- Currency: INR (assumption)
- NumPy: `2.5.5` (the RNG stream is only guaranteed for this version)
- Overall coverage result: **PASS**

## Row counts

| Table | Rows |
| --- | ---: |
| categories | 5 |
| incoming_stock | 113 |
| inventory_levels | 150 |
| inventory_policies | 150 |
| products | 50 |
| sales_daily | 13500 |
| suppliers | 5 |
| warehouses | 3 |

## BP 2.4 minimum scenario counts

| Scenario group | Required | Passing | Result |
| --- | ---: | ---: | --- |
| STOCKOUT | 3 | 3 | PASS |
| CRITICAL | 5 | 5 | PASS |
| HIGH_DEMAND | 4 | 4 | PASS |
| OVERSTOCK | 5 | 5 | PASS |
| SLOW_MOVING + DEAD_STOCK | 6 | 6 | PASS |
| COVERED_BY_INCOMING | 3 | 3 | PASS |
| COMMITTED_MASKING | 3 | 3 | PASS |

## Scenario coverage (design targets, raw-data checks)

| SKU | Warehouse | Scenario | Measured | Target | Result |
| --- | --- | --- | --- | --- | --- |
| SKU-001 | WH-MUM | STOCKOUT | on_hand=10, committed=39, ADS30=21.77, open=[] | committed >= on_hand; ADS30 > 0; no OPEN incoming arriving within L | PASS |
| SKU-002 | WH-MUM | STOCKOUT | on_hand=11, committed=33, ADS30=13.33, open=[] | committed >= on_hand; ADS30 > 0; no OPEN incoming arriving within L | PASS |
| SKU-003 | WH-MUM | STOCKOUT | on_hand=19, committed=38, ADS30=8.57, open=[] | committed >= on_hand; ADS30 > 0; no OPEN incoming arriving within L | PASS |
| SKU-004 | WH-MUM | CRITICAL | DoC=10.36, ADS30=21.53, L=14, open=[] | 0.3L <= DoC <= 0.8L; no OPEN incoming before day floor(DoC) | PASS |
| SKU-005 | WH-MUM | CRITICAL | DoC=14.05, ADS30=2.63, L=21, open=[] | 0.3L <= DoC <= 0.8L; no OPEN incoming before day floor(DoC) | PASS |
| SKU-006 | WH-MUM | CRITICAL | DoC=5.00, ADS30=4.20, L=7, open=[] | 0.3L <= DoC <= 0.8L; no OPEN incoming before day floor(DoC) | PASS |
| SKU-007 | WH-MUM | CRITICAL | DoC=5.10, ADS30=3.33, L=10, open=[] | 0.3L <= DoC <= 0.8L; no OPEN incoming before day floor(DoC) | PASS |
| SKU-008 | WH-MUM | CRITICAL | DoC=9.66, ADS30=4.97, L=14, open=[] | 0.3L <= DoC <= 0.8L; no OPEN incoming before day floor(DoC) | PASS |
| SKU-009 | WH-BLR | HIGH_DEMAND | DoC=21.76, ADS30=3.03, L=21, last14/prior76=2.34 | mean(last 14d) >= 1.5 x mean(prior 76d); L+0.25 <= DoC <= L+1.0 | PASS |
| SKU-010 | WH-BLR | HIGH_DEMAND | DoC=5.36, ADS30=12.50, L=5, last14/prior76=1.83 | mean(last 14d) >= 1.5 x mean(prior 76d); L+0.25 <= DoC <= L+1.0 | PASS |
| SKU-011 | WH-BLR | HIGH_DEMAND | DoC=10.49, ADS30=6.10, L=10, last14/prior76=1.60 | mean(last 14d) >= 1.5 x mean(prior 76d); L+0.25 <= DoC <= L+1.0 | PASS |
| SKU-012 | WH-BLR | HIGH_DEMAND | DoC=14.52, ADS30=3.10, L=14, last14/prior76=2.22 | mean(last 14d) >= 1.5 x mean(prior 76d); L+0.25 <= DoC <= L+1.0 | PASS |
| SKU-013 | WH-DEL | OVERSTOCK | DoC=165.58, ADS30=1.73, L=21 | 150 <= DoC <= 300 | PASS |
| SKU-014 | WH-DEL | OVERSTOCK | DoC=204.65, ADS30=4.30, L=5 | 150 <= DoC <= 300 | PASS |
| SKU-015 | WH-DEL | OVERSTOCK | DoC=188.45, ADS30=6.03, L=7 | 150 <= DoC <= 300 | PASS |
| SKU-016 | WH-DEL | OVERSTOCK | DoC=266.23, ADS30=15.40, L=14 | 150 <= DoC <= 300 | PASS |
| SKU-017 | WH-DEL | OVERSTOCK | DoC=231.90, ADS30=24.70, L=21 | 150 <= DoC <= 300 | PASS |
| SKU-018 | WH-MUM | SLOW_MOVING | DoC=180.00, ADS30=2.60, L=5, ADS30/ADS90=0.34 | ADS30 <= 0.4 x ADS90; on_hand > 0; DoC > 90 | PASS |
| SKU-019 | WH-MUM | SLOW_MOVING | DoC=208.64, ADS30=0.73, L=7, ADS30/ADS90=0.29 | ADS30 <= 0.4 x ADS90; on_hand > 0; DoC > 90 | PASS |
| SKU-020 | WH-MUM | SLOW_MOVING | DoC=240.00, ADS30=0.03, L=10, ADS30/ADS90=0.03 | ADS30 <= 0.4 x ADS90; on_hand > 0; DoC > 90 | PASS |
| SKU-021 | WH-BLR | DEAD_STOCK | units_last_35d=0, on_hand=163 | 0 units in last 35d; on_hand > 0 | PASS |
| SKU-022 | WH-BLR | DEAD_STOCK | units_last_35d=0, on_hand=357 | 0 units in last 35d; on_hand > 0 | PASS |
| SKU-023 | WH-BLR | DEAD_STOCK | units_last_35d=0, on_hand=352 | 0 units in last 35d; on_hand > 0 | PASS |
| SKU-024 | WH-MUM | COVERED_BY_INCOMING | DoC=5.66, ADS30=4.77, L=10, open=[4], qty=115 (need 114) | DoC < L; one OPEN order at t0+max(1,floor(DoC)-1) with qty >= ADS30 x (L+R) | PASS |
| SKU-025 | WH-MUM | COVERED_BY_INCOMING | DoC=7.21, ADS30=6.10, L=14, open=[6], qty=180 (need 171) | DoC < L; one OPEN order at t0+max(1,floor(DoC)-1) with qty >= ADS30 x (L+R) | PASS |
| SKU-026 | WH-MUM | COVERED_BY_INCOMING | DoC=4.06, ADS30=17.00, L=5, open=[3], qty=324 (need 323) | DoC < L; one OPEN order at t0+max(1,floor(DoC)-1) with qty >= ADS30 x (L+R) | PASS |
| SKU-027 | WH-DEL | COMMITTED_MASKING | DoC=3.93, ADS30=3.57, L=7, on_hand=57, committed=43 | on_hand >= 2 x ADS30 x L; 0.2L <= DoC <= 0.7L | PASS |
| SKU-028 | WH-DEL | COMMITTED_MASKING | DoC=3.18, ADS30=2.83, L=10, on_hand=70, committed=61 | on_hand >= 2 x ADS30 x L; 0.2L <= DoC <= 0.7L | PASS |
| SKU-029 | WH-DEL | COMMITTED_MASKING | DoC=3.75, ADS30=1.07, L=14, on_hand=39, committed=35 | on_hand >= 2 x ADS30 x L; 0.2L <= DoC <= 0.7L | PASS |

## HEALTHY product-warehouses

121 of 121 HEALTHY product-warehouses pass (SKU-030 to SKU-050 at all warehouses, plus the non-target warehouses of SKU-001 to SKU-029). Target: L+R+10 <= DoC <= 90; 0 <= committed <= 10% of on_hand.
Measured DoC range: 34.44 to 88.42.

## Category and supplier distribution

| Category | Products |
| --- | ---: |
| ELEC | 10 |
| HOME | 10 |
| PCARE | 10 |
| SPORT | 10 |
| STAT | 10 |

| Supplier | Products |
| --- | ---: |
| SUP-A | 10 |
| SUP-B | 10 |
| SUP-C | 10 |
| SUP-D | 10 |
| SUP-E | 10 |

## Checksums (SHA-256 of canonical CSV, natural keys, rows sorted)

| Table | SHA-256 |
| --- | --- |
| categories | `00f9bc2230555bc3b0595eb219f79020ca349c8d91b640534123748f03c934c0` |
| incoming_stock | `ca0bbd62735eb5edb39ec5361bca5ecaa39e56a8dcf46df3953f9ed1268e7eec` |
| inventory_levels | `c057b9cf2d697dde05c612c177c01b794f80994b9e38ebbff10cc8a0042a7f46` |
| inventory_policies | `61e256f536e2aa9021cb18082a04d1b0096eeb3de0fdb00c0086a5fcdcd656a1` |
| products | `38d49889a273c62418930ba5a40640250e38bfb941f37d0cfffcd16dcb68f187` |
| sales_daily | `f25e213b15393ea02ebaaecaf848aa398d827c40f48aaf6cf24e19c97fd4b425` |
| suppliers | `b270ee8ca6d6c3d5103ea053e88806f7561d78222d875944e8b4f3c2bf711c6c` |
| warehouses | `b55c05d18a984e2014530b28dd5b2ddcc6b6a48c5cc6c00a98224de3ca67876d` |
| **overall** | `e5a3a5fbe8b385814915d5ee77d285c2233c2f1964f581cc31446f0b329bfc62` |

Synthetic data — fictional entities only.
