"""Analytics exceptions. Messages carry keys and field names only, never data dumps."""


class AnalyticsError(Exception):
    """Base class for analytics errors. ``code`` is machine-readable."""

    code = "ANALYTICS_ERROR"


class AnalyticsInputError(AnalyticsError):
    """Structurally invalid input frames (missing, duplicate or negative values)."""

    code = "ANALYTICS_INPUT_ERROR"

    def __init__(self, message: str, keys: list[str] | None = None) -> None:
        self.keys = sorted(keys or [])
        shown = ", ".join(self.keys[:10])
        more = f" (+{len(self.keys) - 10} more)" if len(self.keys) > 10 else ""
        super().__init__(f"{message}: {shown}{more}" if self.keys else message)


class UnsupportedServiceLevelError(AnalyticsError):
    """The service level has no entry in the Z table (no interpolation is ever done)."""

    code = "UNSUPPORTED_SERVICE_LEVEL"

    def __init__(self, service_level: float, supported: list[float]) -> None:
        self.service_level = service_level
        super().__init__(f"Unsupported service level {service_level}; supported: {supported}")
