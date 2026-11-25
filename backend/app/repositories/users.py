"""User repository."""

from collections.abc import Sequence

from sqlalchemy import select

from app.models.governance import User
from app.repositories.base import Repository


class UsersRepository(Repository[User]):
    model = User

    def get_by_username(self, username: str) -> User | None:
        return self.session.scalars(select(User).where(User.username == username)).first()

    def list_all(self) -> Sequence[User]:
        """Every user, by id (the demo set is four rows)."""
        return self.session.scalars(select(User).order_by(User.id)).all()
