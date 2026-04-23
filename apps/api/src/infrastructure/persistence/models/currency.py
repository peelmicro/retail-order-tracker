from uuid import UUID, uuid4

from sqlalchemy import Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.persistence.base import Base, TimestampMixin


class Currency(Base, TimestampMixin):
    __tablename__ = "currencies"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(3), unique=True, nullable=False)
    iso_number: Mapped[str] = mapped_column(String(3), nullable=False)
    symbol: Mapped[str] = mapped_column(String(5), nullable=False)
    decimal_points: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
