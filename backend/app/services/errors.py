"""Service-level errors. Messages carry codes, counts and keys only, never data dumps."""


class ServiceError(Exception):
    """Base class for service errors. ``code`` is machine-readable."""

    code = "SERVICE_ERROR"

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


class RecalculationError(ServiceError):
    """A recalculation failed and was rolled back (no partial snapshot, no audit row).

    ``code`` is the cause's code (an ``AnalyticsError`` code, ``NO_DATA`` or
    ``INVALID_TRIGGERED_BY``). The original exception is chained as ``__cause__``.
    """

    code = "RECALCULATION_FAILED"


class NoDataError(RecalculationError):
    """There is nothing to analyse: ``sales_daily`` is empty, so t0 cannot be derived."""

    code = "NO_DATA"
