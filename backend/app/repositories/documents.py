"""Knowledge document repository (chunks arrive in P7, ADR-014)."""

from app.models.knowledge import Document
from app.repositories.base import Repository


class DocumentRepository(Repository[Document]):
    model = Document
