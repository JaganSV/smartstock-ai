"""Knowledge documents (document_chunks and pgvector are deferred to P7, ADR-014)."""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, ForeignKey, String, false, true
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import CHAR

from app.models.base import Base, created_now, pk_id
from app.models.enums import DocStatus, DocType, check_in


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(check_in("doc_type", DocType), name="doc_type_values"),
        CheckConstraint(check_in("status", DocStatus), name="status_values"),
    )

    id: Mapped[int] = pk_id()
    title: Mapped[str] = mapped_column(String(200))
    doc_type: Mapped[str] = mapped_column(String(32))
    supplier_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("suppliers.id", ondelete="RESTRICT"), index=True
    )
    version: Mapped[str] = mapped_column(String(32), server_default="1.0")
    source_filename: Mapped[str] = mapped_column(String(255))
    sha256: Mapped[str] = mapped_column(CHAR(64), unique=True)
    status: Mapped[str] = mapped_column(String(32), server_default=DocStatus.UPLOADED.value)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=true())
    injection_warning: Mapped[bool] = mapped_column(Boolean, server_default=false())
    uploaded_by: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    uploaded_at: Mapped[datetime] = created_now()
