from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import bcrypt

from src.domain.user import User, UserRole


class InMemoryUserStore:
    """Demo-only user store. In production this would be a SQLAlchemy repository."""

    def __init__(self) -> None:
        self._users: dict[str, User] = {}
        self._password_hashes: dict[str, bytes] = {}

    def add(self, user: User, password: str) -> None:
        self._users[user.username] = user
        self._password_hashes[user.username] = bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt(),
        )

    def get_by_username(self, username: str) -> User | None:
        return self._users.get(username)

    def verify_password(self, username: str, password: str) -> bool:
        hashed = self._password_hashes.get(username)
        if hashed is None:
            return False
        return bcrypt.checkpw(password.encode("utf-8"), hashed)


def _seed() -> InMemoryUserStore:
    store = InMemoryUserStore()
    now = datetime.now(UTC)
    store.add(
        User(
            id=UUID("11111111-1111-1111-1111-111111111111"),
            username="operator",
            email="operator@retail.example",
            role=UserRole.OPERATOR,
            created_at=now,
        ),
        password="operator123",
    )
    store.add(
        User(
            id=UUID("22222222-2222-2222-2222-222222222222"),
            username="admin",
            email="admin@retail.example",
            role=UserRole.ADMIN,
            created_at=now,
        ),
        password="admin123",
    )
    return store


user_store = _seed()
