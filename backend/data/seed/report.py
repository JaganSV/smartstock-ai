"""Coverage checks, canonical table rows, checksums and the Markdown report (section 7.8).

The checks re-measure the *raw generated data* against the generator design targets in
``scenarios.py``. They are not the P2 business formulas and must never be imported by ``app/``.

Checksums use natural keys (SKU, warehouse code, ...) instead of surrogate ids, so the same
dataset has the same checksum in memory and after being read back from the database, and after a
re-seed (identity values keep increasing across delete + insert).
"""

import csv
import hashlib
import io
import math
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

from data.seed.catalog import (
    CATEGORIES,
    CURRENCY,
    SUPPLIERS,
    WAREHOUSES,
    ProductRow,
    SupplierRow,
    WarehouseRow,
)
from data.seed.demand import Demand, IntArray, ads_of, days_of_cover, sales_rows
from data.seed.scenarios import (
    DEAD_DAYS,
    MIN_COUNTS,
    REVIEW_PERIOD_DAYS,
    SCENARIOS,
    SPIKE_DAYS,
    Scenario,
    scenario_at,
)
from data.seed.stock import IncomingRow, LevelRow, StockPlan

EPS = 1e-9
FOOTER = "Synthetic data — fictional entities only."

# Columns per seeded table, in model order, with FK ids replaced by natural keys.
TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "categories": ("code", "name", "description"),
    "incoming_stock": (
        "sku",
        "warehouse_code",
        "supplier_code",
        "quantity",
        "order_date",
        "expected_arrival_date",
        "status",
    ),
    "inventory_levels": ("sku", "warehouse_code", "on_hand_qty", "committed_qty", "as_of"),
    "inventory_policies": (
        "sku",
        "warehouse_code",
        "service_level",
        "review_period_days",
        "safety_stock_override",
        "lead_time_override_days",
    ),
    "products": (
        "sku",
        "name",
        "category_code",
        "supplier_code",
        "unit_cost",
        "unit_price",
        "case_pack",
        "is_active",
        "created_at",
    ),
    "sales_daily": ("sku", "warehouse_code", "sale_date", "units_sold", "revenue"),
    "suppliers": (
        "code",
        "name",
        "default_lead_time_days",
        "lead_time_std_days",
        "min_order_qty",
        "reliability_pct",
        "contact_email",
        "is_active",
    ),
    "warehouses": ("code", "name", "city", "region"),
}  # keys are in table-name order (used for the overall checksum)

TableRows = dict[str, list[tuple[str, ...]]]


@dataclass(frozen=True)
class Dataset:
    seed: int
    as_of: date
    products: tuple[ProductRow, ...]
    demand: Demand
    stock: StockPlan


@dataclass(frozen=True)
class Check:
    sku: str
    warehouse: str
    scenario: Scenario
    measured: str
    target: str
    passed: bool
    doc: float | None


# --- canonical formatting (shared with the DB read-back in generator.py) ---


def fmt_dec(value: Decimal, places: int) -> str:
    return format(value.quantize(Decimal(1).scaleb(-places)), "f")


def fmt_dt(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def fmt_opt(value: int | None) -> str:
    return "" if value is None else str(value)


def fmt_bool(value: bool) -> str:
    return "true" if value else "false"


def canonical_rows(ds: Dataset) -> TableRows:
    products = ds.products
    return {
        "categories": [(c.code, c.name, c.description) for c in CATEGORIES],
        "incoming_stock": [
            (
                r.sku,
                r.warehouse_code,
                r.supplier_code,
                str(r.quantity),
                r.order_date.isoformat(),
                r.expected_arrival_date.isoformat(),
                r.status,
            )
            for r in ds.stock.incoming
        ],
        "inventory_levels": [
            (r.sku, r.warehouse_code, str(r.on_hand), str(r.committed), fmt_dt(r.as_of))
            for r in ds.stock.levels
        ],
        "inventory_policies": [
            (
                r.sku,
                r.warehouse_code,
                fmt_dec(r.service_level, 3),
                str(r.review_period_days),
                fmt_opt(r.safety_stock_override),
                fmt_opt(r.lead_time_override_days),
            )
            for r in ds.stock.policies
        ],
        "products": [
            (
                p.sku,
                p.name,
                p.category_code,
                p.supplier_code,
                fmt_dec(p.unit_cost, 2),
                fmt_dec(p.unit_price, 2),
                str(p.case_pack),
                fmt_bool(True),
                fmt_dt(p.created_at),
            )
            for p in products
        ],
        "sales_daily": [
            (sku, wh, day.isoformat(), str(units), fmt_dec(revenue, 2))
            for sku, wh, day, units, revenue in sales_rows(products, ds.demand)
        ],
        "suppliers": [
            (
                s.code,
                s.name,
                str(s.lead_time_days),
                fmt_dec(s.lead_time_std_days, 2),
                str(s.min_order_qty),
                fmt_dec(s.reliability_pct, 2),
                s.contact_email,
                fmt_bool(True),
            )
            for s in SUPPLIERS
        ],
        "warehouses": [(w.code, w.name, w.city, w.region) for w in WAREHOUSES],
    }


def table_checksum(table: str, rows: list[tuple[str, ...]]) -> str:
    """SHA-256 over the canonical CSV: header, then rows sorted by their canonical values."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(TABLE_COLUMNS[table])
    writer.writerows(sorted(rows))
    return hashlib.sha256(buffer.getvalue().encode("utf-8")).hexdigest()


def checksums(tables: TableRows) -> tuple[dict[str, str], str]:
    """Per-table checksums and one overall checksum over them in table-name order."""
    per_table = {name: table_checksum(name, tables[name]) for name in sorted(TABLE_COLUMNS)}
    joined = "".join(f"{name}:{digest}\n" for name, digest in per_table.items())
    return per_table, hashlib.sha256(joined.encode("utf-8")).hexdigest()


# --- scenario coverage checks ---


@dataclass(frozen=True)
class _Pair:
    product: ProductRow
    warehouse: WarehouseRow
    lead: int
    units: IntArray
    level: LevelRow
    ads30: float
    ads90: float
    doc: float | None
    open_orders: tuple[IncomingRow, ...]
    open_offsets: tuple[int, ...]


def _supplier(code: str) -> SupplierRow:
    return next(s for s in SUPPLIERS if s.code == code)


def _fmt_doc(doc: float | None) -> str:
    return "n/a" if doc is None else f"{doc:.2f}"


def _evaluate(scenario: Scenario, p: _Pair) -> tuple[str, bool]:
    doc, lead, r = p.doc, p.lead, REVIEW_PERIOD_DAYS
    on_hand, committed = p.level.on_hand, p.level.committed
    offsets = list(p.open_offsets)
    head = f"DoC={_fmt_doc(doc)}, ADS30={p.ads30:.2f}, L={lead}"

    if scenario is Scenario.STOCKOUT:
        ok = committed >= on_hand and p.ads30 > 0 and not any(o <= lead for o in offsets)
        return f"on_hand={on_hand}, committed={committed}, ADS30={p.ads30:.2f}, open={offsets}", ok
    if scenario is Scenario.CRITICAL:
        ok = (
            doc is not None
            and 0.3 * lead - EPS <= doc <= 0.8 * lead + EPS
            and not any(o < math.floor(doc) for o in offsets)
        )
        return f"{head}, open={offsets}", ok
    if scenario is Scenario.HIGH_DEMAND:
        recent = int(p.units[-SPIKE_DAYS:].sum())
        prior = int(p.units[:-SPIKE_DAYS].sum())
        ratio = (recent / SPIKE_DAYS) / (prior / (len(p.units) - SPIKE_DAYS)) if prior else 0.0
        # recent/14 >= 1.5 x prior/76  <=>  2 x 76 x recent >= 3 x 14 x prior (exact integers)
        ok = (
            2 * (len(p.units) - SPIKE_DAYS) * recent >= 3 * SPIKE_DAYS * prior
            and doc is not None
            and lead + 0.25 - EPS <= doc <= lead + 1.0 + EPS
        )
        return f"{head}, last14/prior76={ratio:.2f}", ok
    if scenario is Scenario.OVERSTOCK:
        return head, doc is not None and 150 - EPS <= doc <= 300 + EPS
    if scenario is Scenario.SLOW_MOVING:
        s30, s90 = int(p.units[-30:].sum()), int(p.units.sum())
        ok = 15 * s30 <= 2 * s90 and on_hand > 0 and doc is not None and doc > 90
        return f"{head}, ADS30/ADS90={p.ads30 / p.ads90 if p.ads90 else 0.0:.2f}", ok
    if scenario is Scenario.DEAD_STOCK:
        last = int(p.units[-DEAD_DAYS:].sum())
        return f"units_last_{DEAD_DAYS}d={last}, on_hand={on_hand}", last == 0 and on_hand > 0
    if scenario is Scenario.COVERED_BY_INCOMING:
        ok = False
        qty = 0
        if doc is not None and len(p.open_orders) == 1:
            qty = p.open_orders[0].quantity
            ok = (
                doc < lead
                and offsets[0] == max(1, math.floor(doc) - 1)
                and qty >= p.ads30 * (lead + r) - EPS
            )
        return f"{head}, open={offsets}, qty={qty} (need {p.ads30 * (lead + r):.0f})", ok
    if scenario is Scenario.COMMITTED_MASKING:
        ok = (
            doc is not None
            and on_hand >= 2 * p.ads30 * lead - EPS
            and 0.2 * lead - EPS <= doc <= 0.7 * lead + EPS
        )
        return f"{head}, on_hand={on_hand}, committed={committed}", ok
    # HEALTHY
    ok = (
        doc is not None
        and lead + r + 10 - EPS <= doc <= 90 + EPS
        and 0 <= committed <= 0.1 * on_hand
        and all(o > lead for o in offsets)
    )
    return f"{head}, committed={committed}/{on_hand}", ok


def _pairs(ds: Dataset) -> list[_Pair]:
    levels = {(r.sku, r.warehouse_code): r for r in ds.stock.levels}
    open_by_pair: dict[tuple[str, str], list[IncomingRow]] = {}
    for order in ds.stock.incoming:
        if order.status == "OPEN":
            open_by_pair.setdefault((order.sku, order.warehouse_code), []).append(order)
    pairs: list[_Pair] = []
    for i, product in enumerate(ds.products):
        for j, warehouse in enumerate(WAREHOUSES):
            level = levels[(product.sku, warehouse.code)]
            units = ds.demand.units[i, j]
            ads30 = ads_of(units, 30)
            orders = tuple(open_by_pair.get((product.sku, warehouse.code), []))
            pairs.append(
                _Pair(
                    product=product,
                    warehouse=warehouse,
                    lead=_supplier(product.supplier_code).lead_time_days,
                    units=units,
                    level=level,
                    ads30=ads30,
                    ads90=ads_of(units, 90),
                    doc=days_of_cover(level.on_hand, level.committed, ads30),
                    open_orders=orders,
                    open_offsets=tuple((o.expected_arrival_date - ds.as_of).days for o in orders),
                )
            )
    return pairs


def run_checks(ds: Dataset) -> list[Check]:
    """One check per product-warehouse (29 scenario targets + 121 HEALTHY pairs)."""
    targets = {d.scenario: d.target for d in SCENARIOS}
    checks: list[Check] = []
    for pair in _pairs(ds):
        scenario = scenario_at(pair.product.number, pair.warehouse.code)
        measured, ok = _evaluate(scenario, pair)
        checks.append(
            Check(
                sku=pair.product.sku,
                warehouse=pair.warehouse.code,
                scenario=scenario,
                measured=measured,
                target=targets[scenario],
                passed=ok,
                doc=pair.doc,
            )
        )
    return checks


@dataclass(frozen=True)
class MinCount:
    group: str
    required: int
    actual: int

    @property
    def passed(self) -> bool:
        return self.actual >= self.required


def min_counts(checks: list[Check]) -> list[MinCount]:
    """BP 2.4 minimum number of passing scenario SKUs per group."""
    results = []
    for group, scenarios, required in MIN_COUNTS:
        actual = sum(1 for c in checks if c.scenario in scenarios and c.passed)
        results.append(MinCount(group, required, actual))
    return results


def failures(checks: list[Check]) -> list[Check]:
    return [c for c in checks if not c.passed]


def all_passed(checks: list[Check]) -> bool:
    return not failures(checks) and all(m.passed for m in min_counts(checks))


# --- Markdown report ---


def _md_escape(text: str) -> str:
    return text.replace("|", "\\|")


def render_markdown(ds: Dataset, checks: list[Check], numpy_version: str) -> str:
    tables = canonical_rows(ds)
    per_table, overall = checksums(tables)
    scenario_checks = [c for c in checks if c.scenario is not Scenario.HEALTHY]
    healthy = [c for c in checks if c.scenario is Scenario.HEALTHY]
    docs = [c.doc for c in healthy if c.doc is not None]
    verdict = "PASS" if all_passed(checks) else "FAIL"

    lines = [
        "# SmartStock AI — Seed Report",
        "",
        FOOTER,
        "",
        f"- Seed: `{ds.seed}`",
        f"- data_as_of_date (t0): `{ds.as_of.isoformat()}`",
        f"- Sales window: `{ds.demand.days[0].isoformat()}` to `{ds.demand.days[-1].isoformat()}` "
        f"({len(ds.demand.days)} days)",
        f"- Currency: {CURRENCY} (assumption)",
        f"- NumPy: `{numpy_version}` (the RNG stream is only guaranteed for this version)",
        f"- Overall coverage result: **{verdict}**",
        "",
        "## Row counts",
        "",
        "| Table | Rows |",
        "| --- | ---: |",
        *[f"| {name} | {len(tables[name])} |" for name in sorted(tables)],
        "",
        "## BP 2.4 minimum scenario counts",
        "",
        "| Scenario group | Required | Passing | Result |",
        "| --- | ---: | ---: | --- |",
        *[
            f"| {m.group} | {m.required} | {m.actual} | {'PASS' if m.passed else 'FAIL'} |"
            for m in min_counts(checks)
        ],
        "",
        "## Scenario coverage (design targets, raw-data checks)",
        "",
        "| SKU | Warehouse | Scenario | Measured | Target | Result |",
        "| --- | --- | --- | --- | --- | --- |",
        *[
            f"| {c.sku} | {c.warehouse} | {c.scenario.value} | {_md_escape(c.measured)} | "
            f"{_md_escape(c.target)} | {'PASS' if c.passed else 'FAIL'} |"
            for c in scenario_checks
        ],
        "",
        "## HEALTHY product-warehouses",
        "",
        f"{sum(c.passed for c in healthy)} of {len(healthy)} HEALTHY product-warehouses pass "
        f"(SKU-030 to SKU-050 at all warehouses, plus the non-target warehouses of SKU-001 to "
        f"SKU-029). Target: {healthy[0].target if healthy else 'n/a'}.",
        f"Measured DoC range: {min(docs):.2f} to {max(docs):.2f}." if docs else "",
        "",
        "## Category and supplier distribution",
        "",
        "| Category | Products |",
        "| --- | ---: |",
        *[
            f"| {cat.code} | {sum(1 for p in ds.products if p.category_code == cat.code)} |"
            for cat in CATEGORIES
        ],
        "",
        "| Supplier | Products |",
        "| --- | ---: |",
        *[
            f"| {s.code} | {sum(1 for p in ds.products if p.supplier_code == s.code)} |"
            for s in SUPPLIERS
        ],
        "",
        "## Checksums (SHA-256 of canonical CSV, natural keys, rows sorted)",
        "",
        "| Table | SHA-256 |",
        "| --- | --- |",
        *[f"| {name} | `{digest}` |" for name, digest in per_table.items()],
        f"| **overall** | `{overall}` |",
        "",
        FOOTER,
        "",
    ]
    return "\n".join(lines)
