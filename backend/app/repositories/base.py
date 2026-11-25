"""Generic repository base. No business logic; callers own the transaction (no commit here)."""

from collections.abc import Collection, Sequence
from typing import Any

from sqlalchemy import Select, SQLColumnExpression, select
from sqlalchemy.orm import Session

from app.models.base import Base

MAX_LIST_LIMIT = 100


def where_in[*Ts](
    stmt: Select[*Ts], column: SQLColumnExpression[Any], values: Collection[Any] | None
) -> Select[*Ts]:
    """``stmt`` restricted to ``column IN values``; unchanged when ``values`` is None."""
    return stmt if values is None else stmt.where(column.in_(list(values)))


class Repository[ModelT: Base]:
    """get / list / add for one mapped class.

    ``add`` flushes (so generated ids and constraint violations surface immediately as
    ``IntegrityError``) but never commits.
    """

    model: type[ModelT]

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, id: Any) -> ModelT | None:
        return self.session.get(self.model, id)

    def list(self, offset: int = 0, limit: int = 50) -> Sequence[ModelT]:
        if offset < 0:
            raise ValueError("offset must be >= 0")
        if not 1 <= limit <= MAX_LIST_LIMIT:
            raise ValueError(f"limit must be between 1 and {MAX_LIST_LIMIT}")
        primary_key = self.model.__mapper__.primary_key
        stmt = select(self.model).order_by(*primary_key).offset(offset).limit(limit)
        return self.session.scalars(stmt).all()

    def add(self, entity: ModelT) -> ModelT:
        self.session.add(entity)
        self.session.flush()
        return entity
