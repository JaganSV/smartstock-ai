"""Metric snapshot and per-product metric repositories."""

from sqlalchemy import select

from app.models.analytics import MetricSnapshot, ProductMetric
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


class ProductMetricRepository(Repository[ProductMetric]):
    model = ProductMetric
