from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class UserRole(StrEnum):
    OPERATOR = "operator"
    ADMIN = "admin"


@dataclass(frozen=True, slots=True)
class User:
    id: UUID
    username: str
    email: str
    role: UserRole
    created_at: datetime
    disabled_at: datetime | None = None

    @property
    def is_active(self) -> bool:
        return self.disabled_at is None
