"""Python mirrors of the VARCHAR(32)+CHECK value sets (no native PostgreSQL ENUM types)."""

from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "ADMIN"
    INVENTORY_MANAGER = "INVENTORY_MANAGER"
    ANALYST = "ANALYST"
    EXECUTIVE = "EXECUTIVE"


class IncomingStatus(StrEnum):
    OPEN = "OPEN"
    RECEIVED = "RECEIVED"
    CANCELLED = "CANCELLED"


class RiskClass(StrEnum):
    STOCKOUT = "STOCKOUT"
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    OVERSTOCK = "OVERSTOCK"
    LOW = "LOW"


# Most severe first (BP 7.4 roll-ups). DB values are the unchanged StrEnum values above.
RISK_SEVERITY: tuple[RiskClass, ...] = (
    RiskClass.STOCKOUT,
    RiskClass.CRITICAL,
    RiskClass.HIGH,
    RiskClass.MEDIUM,
    RiskClass.OVERSTOCK,
    RiskClass.LOW,
)
RISK_RANK: dict[str, int] = {risk.value: rank for rank, risk in enumerate(RISK_SEVERITY)}


class RecommendationStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    ADJUSTED_APPROVED = "ADJUSTED_APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class Decision(StrEnum):
    APPROVE = "APPROVE"
    ADJUST = "ADJUST"
    REJECT = "REJECT"


class ReportScope(StrEnum):
    ALL = "ALL"
    WAREHOUSE = "WAREHOUSE"
    CATEGORY = "CATEGORY"


class DocType(StrEnum):
    SUPPLIER_POLICY = "SUPPLIER_POLICY"
    SOP = "SOP"


class DocStatus(StrEnum):
    UPLOADED = "UPLOADED"
    INDEXED = "INDEXED"
    FAILED = "FAILED"


class AiFeature(StrEnum):
    COPILOT = "COPILOT"
    KNOWLEDGE = "KNOWLEDGE"
    REPLENISHMENT = "REPLENISHMENT"
    REPORT = "REPORT"
    INTENT = "INTENT"


class ValidationStatus(StrEnum):
    PASSED = "PASSED"
    FAILED_SCHEMA = "FAILED_SCHEMA"
    FAILED_GROUNDING = "FAILED_GROUNDING"
    BLOCKED_INPUT = "BLOCKED_INPUT"
    ERROR = "ERROR"


def check_in(column: str, values: type[StrEnum]) -> str:
    """SQL text for a CHECK listing the allowed values, e.g. ``role IN ('A', 'B')``."""
    listed = ", ".join(f"'{member.value}'" for member in values)
    return f"{column} IN ({listed})"
