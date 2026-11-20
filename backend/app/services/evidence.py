"""Evidence report for a snapshot: class distribution, Table 7.8 verification, KPIs (BOB-P2-02).

Rendered from the PERSISTED snapshot rows (read back through the repository), so the report shows
what the API and the UI will read. ``SCENARIO_EXPECTATIONS`` mirrors the engineered seed scenarios
(BP 2.4 / BOB-P2-02 Table 7.8); it describes the synthetic seed and is used for evidence only.
"""

from dataclasses import dataclass
from typing import Any

import pandas as pd

from app.analytics.flags import is_high_demand
from app.analytics.params import AnalyticsParams
from app.analytics.rollup import dashboard_kpis, risk_distribution, rollup_by_product
from app.services.analytics_service import RecalculationService, SnapshotResult


@dataclass(frozen=True)
class ScenarioExpectation:
    scenario: str
    first_sku: int
    last_sku: int
    warehouse_code: str
    risk_classes: frozenset[str]
    flags: tuple[str, ...]  # flag columns that must be True
    extra: str = ""  # human-readable extra condition (checked in ``_extra_ok``)


SCENARIO_EXPECTATIONS: tuple[ScenarioExpectation, ...] = (
    ScenarioExpectation("STOCKOUT", 1, 3, "WH-MUM", frozenset({"STOCKOUT"}), ()),
    ScenarioExpectation("CRITICAL", 4, 8, "WH-MUM", frozenset({"CRITICAL"}), ()),
    ScenarioExpectation("HIGH_DEMAND", 9, 12, "WH-BLR", frozenset({"HIGH"}), ("is_high_demand",)),
    ScenarioExpectation("OVERSTOCK", 13, 17, "WH-DEL", frozenset({"OVERSTOCK"}), ()),
    ScenarioExpectation(
        "SLOW_MOVING", 18, 20, "WH-MUM", frozenset({"LOW", "OVERSTOCK"}), ("is_slow_moving",)
    ),
    ScenarioExpectation(
        "DEAD_STOCK",
        21,
        23,
        "WH-BLR",
        frozenset({"OVERSTOCK"}),
        ("is_dead_stock", "is_slow_moving"),
        "reason R5 (ADS30 = 0)",
    ),
    ScenarioExpectation(
        "COVERED_BY_INCOMING",
        24,
        26,
        "WH-MUM",
        frozenset({"MEDIUM"}),
        (),
        "incoming_in_lt > 0; no projected stockout",
    ),
    ScenarioExpectation("COMMITTED_MASKING", 27, 29, "WH-DEL", frozenset({"CRITICAL"}), ()),
)


def sku_number(sku: str) -> int:
    return int(sku.split("-")[1])


def expectation_for(sku: str, warehouse_code: str) -> ScenarioExpectation | None:
    """The scenario row expectation, or None for a HEALTHY row."""
    number = sku_number(sku)
    for item in SCENARIO_EXPECTATIONS:
        if item.first_sku <= number <= item.last_sku and item.warehouse_code == warehouse_code:
            return item
    return None


def _flag(row: Any, name: str) -> bool:
    return bool(row[name])


def check_row(row: Any, params: AnalyticsParams) -> tuple[bool, str]:
    """(passed, detail) for one stored row against Table 7.8."""
    expected = expectation_for(str(row["sku"]), str(row["warehouse_code"]))
    flags = {
        "is_slow_moving": bool(row["is_slow_moving"]),
        "is_dead_stock": bool(row["is_dead_stock"]),
        "is_high_demand": bool(
            is_high_demand(pd.DataFrame({"demand_trend": [row["demand_trend"]]}), params)[0]
        ),
    }
    if expected is None:  # HEALTHY: LOW with no persisted flags
        ok = (
            row["risk_class"] == "LOW"
            and not flags["is_slow_moving"]
            and not flags["is_dead_stock"]
        )
        return ok, f"class {row['risk_class']}"
    ok = row["risk_class"] in expected.risk_classes
    ok = ok and all(flags[name] for name in expected.flags)
    if expected.scenario == "DEAD_STOCK":
        ok = ok and row["risk_reason_code"] == "R5_EXCESS_COVER"
    if expected.scenario == "COVERED_BY_INCOMING":
        ok = ok and int(row["incoming_in_lt"]) > 0
    return ok, f"class {row['risk_class']} ({row['risk_reason_code']})"


def _mark(passed: bool) -> str:
    return "PASS" if passed else "FAIL"


def _table(headers: list[str], rows: list[list[str]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(cells) + " |" for cells in rows)
    return lines


def render_risk_distribution_report(service: RecalculationService, result: SnapshotResult) -> str:
    """Markdown evidence for ``result``'s snapshot (rows read back from the database)."""
    params = AnalyticsParams(t0=result.t0)
    stored = service.stored_metrics(result.snapshot_id)
    products = service.active_products()
    rolled = rollup_by_product(stored)
    row_counts = risk_distribution(stored)
    product_counts = {risk: int((rolled["risk_class"] == risk).sum()) for risk in row_counts}
    kpis = dashboard_kpis(stored, products)

    lines = [
        "# P2 risk distribution (BOB-P2-02)",
        "",
        f"- Snapshot id: {result.snapshot_id}",
        f"- data_as_of_date (t0): {result.t0.isoformat()}",
        f"- Stored rows: {len(stored)}",
        f"- Recalculation time: {result.duration_ms} ms (NFR-03: under 5000 ms)",
        "- Source: the persisted `product_metrics` rows of this snapshot.",
        "- Synthetic data only.",
        "",
        "## Class distribution",
        "",
        *_table(
            ["Risk class", "Product x warehouse rows", "Products (most severe warehouse)"],
            [[risk, str(row_counts[risk]), str(product_counts[risk])] for risk in row_counts],
        ),
        "",
        f"All six classes present: **{_mark(all(count > 0 for count in row_counts.values()))}**",
        "",
        "## Table 7.8 verification (scenario rows)",
        "",
    ]
    scenario_rows: list[list[str]] = []
    failures = 0
    healthy_total = healthy_passed = 0
    for _, row in stored.iterrows():
        passed, detail = check_row(row, params)
        expected = expectation_for(str(row["sku"]), str(row["warehouse_code"]))
        if expected is None:
            healthy_total += 1
            healthy_passed += int(passed)
            if not passed:
                scenario_rows.append(
                    [str(row["sku"]), str(row["warehouse_code"]), "HEALTHY", "LOW", detail, "FAIL"]
                )
            failures += int(not passed)
            continue
        failures += int(not passed)
        scenario_rows.append(
            [
                str(row["sku"]),
                str(row["warehouse_code"]),
                expected.scenario,
                "/".join(sorted(expected.risk_classes))
                + (f"; {'+'.join(expected.flags)}" if expected.flags else "")
                + (f"; {expected.extra}" if expected.extra else ""),
                detail,
                _mark(passed),
            ]
        )
    scenario_rows.sort(key=lambda cells: (cells[0], cells[1]))
    lines += _table(["SKU", "Warehouse", "Scenario", "Expected", "Actual", "Result"], scenario_rows)
    lines += [
        "",
        f"HEALTHY rows (all other product x warehouse pairs): {healthy_passed} of "
        f"{healthy_total} are LOW with no slow-moving or dead-stock flag: "
        f"**{_mark(healthy_passed == healthy_total)}**",
        "",
        f"Overall Table 7.8: **{_mark(failures == 0)}**",
        "",
        "## Dashboard KPIs (FR-A1, whole company)",
        "",
        *_table(
            ["KPI", "Value"],
            [
                ["total_products", str(kpis["total_products"])],
                ["total_units", str(kpis["total_units"])],
                ["inventory_value", str(kpis["inventory_value"])],
                ["low_stock_count (products HIGH or MEDIUM)", str(kpis["low_stock_count"])],
                [
                    "stockout_risk_count (products STOCKOUT, CRITICAL or HIGH)",
                    str(kpis["stockout_risk_count"]),
                ],
                ["slow_moving_count (products)", str(kpis["slow_moving_count"])],
            ],
        ),
        "",
    ]
    return "\n".join(lines) + "\n"
