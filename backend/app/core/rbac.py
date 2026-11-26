"""Role matrix as data (BP 10.2, binding). Routes ask for a capability, never for a role list.

Capability keys are the left column of the BP 10.2 table. Do not add, remove or rename a
capability without an architect decision. ``GET /auth/me`` is open to any authenticated role and is
not a matrix capability; it returns the caller's capability keys (``capabilities_for``).
"""

from collections.abc import Mapping

from app.models.enums import UserRole

ADMIN = UserRole.ADMIN
MANAGER = UserRole.INVENTORY_MANAGER
ANALYST = UserRole.ANALYST
EXECUTIVE = UserRole.EXECUTIVE

ALL_ROLES: frozenset[UserRole] = frozenset(UserRole)

ROLE_MATRIX: Mapping[str, frozenset[UserRole]] = {
    # View dashboard, risk, analytics, products (also GET of reports and documents)
    "view_inventory": frozenset({ADMIN, MANAGER, ANALYST, EXECUTIVE}),
    # Ask copilot / knowledge assistant
    "ask_ai": frozenset({ADMIN, MANAGER, ANALYST, EXECUTIVE}),
    # Generate replenishment recommendations
    "generate_recommendations": frozenset({ADMIN, MANAGER}),
    # Approve / adjust / reject recommendations
    "decide_recommendations": frozenset({ADMIN, MANAGER}),
    # Export approved recommendations CSV
    "export_approved_csv": frozenset({ADMIN, MANAGER}),
    # Generate executive report
    "generate_executive_report": frozenset({ADMIN, MANAGER, EXECUTIVE}),
    # Upload / manage knowledge documents
    "manage_documents": frozenset({ADMIN}),
    # Trigger analytics recalculation
    "recalculate_analytics": frozenset({ADMIN}),
    # View audit log and AI interactions
    "view_governance": frozenset({ADMIN}),
}


def allowed_roles(capability: str) -> frozenset[UserRole]:
    """Roles that hold ``capability``. An unknown capability is a programming error (KeyError)."""
    return ROLE_MATRIX[capability]


def capabilities_for(role: UserRole | str) -> list[str]:
    """The capability keys ``role`` holds in ``ROLE_MATRIX``, sorted (``GET /auth/me``, P4-01).

    The frontend decides what to show from this list only; the routes still enforce every check.
    """
    return sorted(key for key, roles in ROLE_MATRIX.items() if role in roles)
