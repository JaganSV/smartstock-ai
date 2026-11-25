"""Shared API schemas: the generic page envelope and its query parameters (BP 6.1)."""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Query
from pydantic import BaseModel

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
