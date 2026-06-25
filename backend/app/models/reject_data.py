"""Rejected persist payloads (firewall and persist_module)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, DateTime, Identity, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class RejectData(Base):
    """Rich diagnostic store for firewall and persist rejections."""

    __tablename__ = "reject_data"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    table_target: Mapped[str] = mapped_column(String(50), nullable=False)
    operation: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        server_default=text("'insert'"),
    )
    marketplace_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    listing_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    reject_reason: Mapped[str] = mapped_column(String(100), nullable=False)
    failed_rules: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    signature_present: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rejected_by: Mapped[str] = mapped_column(String(20), nullable=False)

    __table_args__ = (
        Index("idx_reject_data_created_at", "created_at"),
        Index("idx_reject_data_source", "source"),
        Index("idx_reject_data_reject_reason", "reject_reason"),
    )
