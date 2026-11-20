"""Metric snapshot and per-product metric repositories (no business rules, no DataFrames)."""

from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import RowMapping, func, insert, select

from app.models.analytics import MetricSnapshot, ProductMetric
from app.models.product import Product
from app.models.reference import Warehouse
from app.repositories.base import Repository


class MetricsRepository(Repository[MetricSnapshot]):
    model = MetricSnapshot

    def latest_snapshot(self) -> MetricSnapshot | None:
        """Newest snapshot by ``calculated_at`` (ties broken by highest id)."""
        stmt = (
            select(MetricSnapshot)
            .order_by(MetricSnapshot.calculated_at.desc(), MetricSnapshot.id.desc())
            .limit(1)
        )
        return self.session.scalars(stmt).first()

    def add_snapshot_metrics(self, snapshot_id: int, rows: Sequence[Mapping[str, Any]]) -> int:
        """Bulk-insert ``product_metrics`` rows for a snapshot (one INSERT, executemany).

        Each row holds the ``product_metrics`` column values without ``snapshot_id``. Flushes
        through the session but never commits. Returns the number of rows written.
        """
        if not rows:
            return 0
        self.session.execute(
            insert(ProductMetric), [{**row, "snapshot_id": snapshot_id} for row in rows]
        )
        self.session.flush()
        return len(rows)

    def count_snapshots(self) -> int:
        return int(
            self.session.execute(select(func.count()).select_from(MetricSnapshot)).scalar_one()
        )

    def snapshot_metric_rows(self, snapshot_id: int) -> Sequence[RowMapping]:
        """Every stored metric row of a snapshot with its SKU and warehouse code.

        Columns: the ``product_metrics`` columns (minus id and snapshot_id), then ``sku`` and
        ``warehouse_code``. Ordered by product id, warehouse id.
        """
        columns = [
            column
            for column in ProductMetric.__table__.columns
            if column.name not in {"id", "snapshot_id"}
        ]
        stmt = (
            select(*columns, Product.sku, Warehouse.code.label("warehouse_code"))
            .join(Product, Product.id == ProductMetric.product_id)
            .join(Warehouse, Warehouse.id == ProductMetric.warehouse_id)
            .where(ProductMetric.snapshot_id == snapshot_id)
            .order_by(ProductMetric.product_id, ProductMetric.warehouse_id)
        )
        return self.session.execute(stmt).mappings().all()


class ProductMetricRepository(Repository[ProductMetric]):
    model = ProductMetric
