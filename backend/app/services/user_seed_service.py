"""Create or update the four demo users (``python -m app.cli seed-users``).

Local and test environments only. Passwords come from the ``SEED_USER_PASSWORD_*`` settings, are
validated before anything is written, and are never logged, printed or audited. The running app
never reads these settings. Idempotent: a second run updates the same four rows.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.governance import AuditLog, User
from app.repositories.audit import AuditRepository
from app.repositories.users import UsersRepository
from app.services.errors import SeedUsersRefusedError

ALLOWED_ENVS = ("local", "test")
MIN_PASSWORD_CHARS = 12
PLACEHOLDER_PREFIX = "change_me"  # the .env.example placeholder
USER_SEEDED = "USER_SEEDED"

# (username, role, name of the settings attribute that holds the password)
DEMO_USERS: tuple[tuple[str, UserRole, str], ...] = (
    ("admin", UserRole.ADMIN, "seed_user_password_admin"),
    ("manager", UserRole.INVENTORY_MANAGER, "seed_user_password_manager"),
    ("analyst", UserRole.ANALYST, "seed_user_password_analyst"),
    ("executive", UserRole.EXECUTIVE, "seed_user_password_executive"),
)


@dataclass(frozen=True)
class SeededUser:
    username: str
    role: str
    outcome: str  # "created" | "updated"


def _passwords(settings: Settings) -> dict[str, str]:
    """username -> password, or ``SeedUsersRefusedError`` naming the setting (never its value)."""
    result: dict[str, str] = {}
    for username, _role, attribute in DEMO_USERS:
        secret = getattr(settings, attribute)
        name = attribute.upper()
        if secret is None:
            raise SeedUsersRefusedError(f"{name} is not set")
        value: str = secret.get_secret_value()
        if len(value) < MIN_PASSWORD_CHARS:
            raise SeedUsersRefusedError(f"{name} must be at least {MIN_PASSWORD_CHARS} characters")
        if value.lower().startswith(PLACEHOLDER_PREFIX):
            raise SeedUsersRefusedError(f"{name} is still the .env.example placeholder")
        result[username] = value
    return result


def seed_users(session: Session, settings: Settings) -> list[SeededUser]:
    """Validate, then create or update the four users and audit each one, in one transaction."""
    if settings.app_env not in ALLOWED_ENVS:
        raise SeedUsersRefusedError(
            f"APP_ENV is {settings.app_env!r}; seeding users only runs when it is "
            f"{' or '.join(ALLOWED_ENVS)}"
        )
    passwords = _passwords(settings)  # everything is validated before the first write
    users, audit = UsersRepository(session), AuditRepository(session)
    seeded: list[SeededUser] = []
    try:
        for username, role, _attribute in DEMO_USERS:
            password_hash = hash_password(passwords[username])
            user = users.get_by_username(username)
            if user is None:
                user = users.add(
                    User(
                        username=username,
                        password_hash=password_hash,
                        role=role.value,
                        is_active=True,
                    )
                )
                outcome = "created"
            else:
                user.password_hash = password_hash
                user.role = role.value
                user.is_active = True
                session.flush()
                outcome = "updated"
            audit.add(
                AuditLog(
                    action=USER_SEEDED,
                    entity_type="user",
                    entity_id=username,
                    details={"username": username, "role": role.value, "outcome": outcome},
                )
            )
            seeded.append(SeededUser(username, role.value, outcome))
        session.commit()
    except Exception:
        session.rollback()
        raise
    return seeded
