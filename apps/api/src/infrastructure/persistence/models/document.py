from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.persistence.base import Base, TimestampMixin
from src.infrastructure.persistence.models.format import Format


class Document(Base, TimestampMixin):
    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    filename: Mapped[str] = mapped_column(String(200), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)

    format_id: Mapped[UUID] = mapped_column(
        ForeignKey("formats.id", ondelete="RESTRICT"),
        nullable=False,
    )
    format: Mapped[Format] = relationship()
