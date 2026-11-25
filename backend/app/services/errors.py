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


class AuthenticationError(ServiceError):
    """Wrong username or password, or an inactive user. One generic message for all of them."""

    code = "UNAUTHENTICATED"


class AccountLockedError(ServiceError):
    """Too many recent failed logins for this username. ``retry_after`` is in seconds."""

    code = "RATE_LIMITED"

    def __init__(self, retry_after: int) -> None:
        super().__init__("Too many failed login attempts. Try again later.")
        self.retry_after = retry_after


class SeedUsersRefusedError(ServiceError):
    """``seed-users`` refused to run (environment or password rules); names settings only."""

    code = "SEED_USERS_REFUSED"


class NotFoundError(ServiceError):
    """An id in the path or a filter does not exist. The message names the kind of id only."""

    code = "NOT_FOUND"


class NoSnapshotError(ServiceError):
    """No ``metric_snapshot`` exists yet, so snapshot-derived data cannot be served (409)."""

    code = "CONFLICT"

    def __init__(self) -> None:
        super().__init__("No analytics snapshot available. Run a recalculation.")


class NoSalesDataError(ServiceError):
    """``sales_daily`` is empty and there is no snapshot, so t0 cannot be derived (409)."""

    code = "CONFLICT"

    def __init__(self) -> None:
        super().__init__("No sales data available.")


class SnapshotStaleError(ServiceError):
    """Recomputed values differ from the stored snapshot row (FR-B6), so nothing is served (409).

    ``fields`` names the mismatched metrics only, never their values.
    """

    code = "CONFLICT"

    def __init__(self, fields: list[str]) -> None:
        super().__init__("Underlying data has changed since this snapshot. Run a recalculation.")
        self.fields = fields


class RecalculationLockedError(RecalculationError):
    """Another recalculation holds the advisory lock; this one did not run (409 on the API)."""

    code = "LOCK_HELD"

    def __init__(self) -> None:
        super().__init__("A recalculation is already running.")
