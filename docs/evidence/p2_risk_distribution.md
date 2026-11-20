# P2 risk distribution (BOB-P2-02)

- Snapshot id: 2
- data_as_of_date (t0): 2026-09-30
- Stored rows: 150
- Recalculation time: 195 ms (NFR-03: under 5000 ms)
- Source: the persisted `product_metrics` rows of this snapshot.
- Synthetic data only.

## Class distribution

| Risk class | Product x warehouse rows | Products (most severe warehouse) |
| --- | --- | --- |
| STOCKOUT | 3 | 3 |
| CRITICAL | 8 | 8 |
| HIGH | 4 | 4 |
| MEDIUM | 3 | 3 |
| OVERSTOCK | 11 | 11 |
| LOW | 121 | 21 |

All six classes present: **PASS**

## Table 7.8 verification (scenario rows)

| SKU | Warehouse | Scenario | Expected | Actual | Result |
| --- | --- | --- | --- | --- | --- |
| SKU-001 | WH-MUM | STOCKOUT | STOCKOUT | class STOCKOUT (R1_NO_AVAILABLE_STOCK) | PASS |
| SKU-002 | WH-MUM | STOCKOUT | STOCKOUT | class STOCKOUT (R1_NO_AVAILABLE_STOCK) | PASS |
| SKU-003 | WH-MUM | STOCKOUT | STOCKOUT | class STOCKOUT (R1_NO_AVAILABLE_STOCK) | PASS |
| SKU-004 | WH-MUM | CRITICAL | CRITICAL | class CRITICAL (R2_STOCKOUT_BEFORE_REPLENISHMENT) | PASS |
| SKU-005 | WH-MUM | CRITICAL | CRITICAL | class CRITICAL (R2_STOCKOUT_BEFORE_REPLENISHMENT) | PASS |
| SKU-006 | WH-MUM | CRITICAL | CRITICAL | class CRITICAL (R2_STOCKOUT_BEFORE_REPLENISHMENT) | PASS |
| SKU-007 | WH-MUM | CRITICAL | CRITICAL | class CRITICAL (R2_STOCKOUT_BEFORE_REPLENISHMENT) | PASS |
| SKU-008 | WH-MUM | CRITICAL | CRITICAL | class CRITICAL (R2_STOCKOUT_BEFORE_REPLENISHMENT) | PASS |
| SKU-009 | WH-BLR | HIGH_DEMAND | HIGH; is_high_demand | class HIGH (R3_BELOW_REORDER_POINT) | PASS |
| SKU-010 | WH-BLR | HIGH_DEMAND | HIGH; is_high_demand | class HIGH (R3_BELOW_REORDER_POINT) | PASS |
| SKU-011 | WH-BLR | HIGH_DEMAND | HIGH; is_high_demand | class HIGH (R3_BELOW_REORDER_POINT) | PASS |
| SKU-012 | WH-BLR | HIGH_DEMAND | HIGH; is_high_demand | class HIGH (R3_BELOW_REORDER_POINT) | PASS |
| SKU-013 | WH-DEL | OVERSTOCK | OVERSTOCK | class OVERSTOCK (R5_EXCESS_COVER) | PASS |
| SKU-014 | WH-DEL | OVERSTOCK | OVERSTOCK | class OVERSTOCK (R5_EXCESS_COVER) | PASS |
| SKU-015 | WH-DEL | OVERSTOCK | OVERSTOCK | class OVERSTOCK (R5_EXCESS_COVER) | PASS |
| SKU-016 | WH-DEL | OVERSTOCK | OVERSTOCK | class OVERSTOCK (R5_EXCESS_COVER) | PASS |
| SKU-017 | WH-DEL | OVERSTOCK | OVERSTOCK | class OVERSTOCK (R5_EXCESS_COVER) | PASS |
| SKU-018 | WH-MUM | SLOW_MOVING | LOW/OVERSTOCK; is_slow_moving | class OVERSTOCK (R5_EXCESS_COVER) | PASS |
| SKU-019 | WH-MUM | SLOW_MOVING | LOW/OVERSTOCK; is_slow_moving | class OVERSTOCK (R5_EXCESS_COVER) | PASS |
| SKU-020 | WH-MUM | SLOW_MOVING | LOW/OVERSTOCK; is_slow_moving | class OVERSTOCK (R5_EXCESS_COVER) | PASS |
| SKU-021 | WH-BLR | DEAD_STOCK | OVERSTOCK; is_dead_stock+is_slow_moving; reason R5 (ADS30 = 0) | class OVERSTOCK (R5_EXCESS_COVER) | PASS |
| SKU-022 | WH-BLR | DEAD_STOCK | OVERSTOCK; is_dead_stock+is_slow_moving; reason R5 (ADS30 = 0) | class OVERSTOCK (R5_EXCESS_COVER) | PASS |
| SKU-023 | WH-BLR | DEAD_STOCK | OVERSTOCK; is_dead_stock+is_slow_moving; reason R5 (ADS30 = 0) | class OVERSTOCK (R5_EXCESS_COVER) | PASS |
| SKU-024 | WH-MUM | COVERED_BY_INCOMING | MEDIUM; incoming_in_lt > 0; no projected stockout | class MEDIUM (R4_COVER_BELOW_LEAD_PLUS_REVIEW) | PASS |
| SKU-025 | WH-MUM | COVERED_BY_INCOMING | MEDIUM; incoming_in_lt > 0; no projected stockout | class MEDIUM (R4_COVER_BELOW_LEAD_PLUS_REVIEW) | PASS |
| SKU-026 | WH-MUM | COVERED_BY_INCOMING | MEDIUM; incoming_in_lt > 0; no projected stockout | class MEDIUM (R4_COVER_BELOW_LEAD_PLUS_REVIEW) | PASS |
| SKU-027 | WH-DEL | COMMITTED_MASKING | CRITICAL | class CRITICAL (R2_STOCKOUT_BEFORE_REPLENISHMENT) | PASS |
| SKU-028 | WH-DEL | COMMITTED_MASKING | CRITICAL | class CRITICAL (R2_STOCKOUT_BEFORE_REPLENISHMENT) | PASS |
| SKU-029 | WH-DEL | COMMITTED_MASKING | CRITICAL | class CRITICAL (R2_STOCKOUT_BEFORE_REPLENISHMENT) | PASS |

HEALTHY rows (all other product x warehouse pairs): 121 of 121 are LOW with no slow-moving or dead-stock flag: **PASS**

Overall Table 7.8: **PASS**

## Dashboard KPIs (FR-A1, whole company)

| KPI | Value |
| --- | --- |
| total_products | 50 |
| total_units | 73484 |
| inventory_value | 89944367.37 |
| low_stock_count (products HIGH or MEDIUM) | 7 |
| stockout_risk_count (products STOCKOUT, CRITICAL or HIGH) | 15 |
| slow_moving_count (products) | 11 |

