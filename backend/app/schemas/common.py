"""Shared API schemas: the page envelope, its query parameters (BP 6.1) and value types."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import Query
from pydantic import AfterValidator, BaseModel, Field, PlainSerializer

from app.analytics.numeric import money, round_decimal

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100


class Page[T](BaseModel):
    """``{items, page, page_size, total}``."""

    items: list[T]
    page: int
    page_size: int
    total: int


@dataclass(frozen=True)
class PageParams:
    page: int
    page_size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def page_params(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
) -> PageParams:
    """Dependency: ``page`` >= 1, ``page_size`` 1 to 100; out of range gives 422."""
    return PageParams(page=page, page_size=page_size)


# --- shared value types for verified-data responses (BOB-P3-02a) ---


def _money_text(value: Decimal) -> str:
    return str(money(value))


def _four_dp(value: float) -> float:
    return float(round_decimal(value, 4))


Money = Annotated[
    Decimal,
    PlainSerializer(_money_text, return_type=str),
    Field(
        description=(
            'Money as a decimal string with exactly 2 decimal places (e.g. "89944367.37"), '
            "never a float."
        )
    ),
]
"""Monetary value, serialised as a 2-dp decimal string (ROUND_HALF_UP)."""

FourDp = Annotated[float, AfterValidator(_four_dp)]
"""ADS, days of cover and trend values: JSON numbers rounded to 4 dp (ROUND_HALF_UP)."""


class SnapshotMeta(BaseModel):
    """Which analytics snapshot the numbers come from (FR-A5: "Verified · calculated <time>")."""

    snapshot_id: int
    calculated_at: datetime
    data_as_of_date: date = Field(description="t0 of the snapshot (ADR-012).")
    verified: Literal[True] = True
