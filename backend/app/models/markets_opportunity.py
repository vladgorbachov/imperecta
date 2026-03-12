"""Opportunity blocks. Actionable insights refreshed every 2 hours."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class MarketsOpportunityBlock(Base):
    """Opportunity block: actionable insight with metrics."""

    __tablename__ = "markets_opportunities"
    __table_args__ = (
        Index("ix_markets_opportunities_type", "block_type"),
        Index("ix_markets_opportunities_refreshed", "refreshed_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    block_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    refreshed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
