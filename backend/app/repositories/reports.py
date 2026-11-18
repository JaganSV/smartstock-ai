"""Executive report repository."""

from app.models.reports import ExecutiveReport
from app.repositories.base import Repository


class ExecutiveReportRepository(Repository[ExecutiveReport]):
    model = ExecutiveReport
