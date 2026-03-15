"""Competitor model."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class Competitor(Base):
    """Competitor marketplace or store."""

    __tablename__ = "competitors"
    __table_args__ = (Index("ix_competitors_user_id", "user_id"),)

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    website_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    marketplace: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # marketplace identifier, any string
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="competitors")
    competitor_products: Mapped[list["CompetitorProduct"]] = relationship(
        "CompetitorProduct",
        back_populates="competitor",
        cascade="all, delete-orphan",
    )
