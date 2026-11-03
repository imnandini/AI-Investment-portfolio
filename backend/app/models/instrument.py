from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Index, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Instrument(Base):
    __tablename__ = "instruments"
    __table_args__ = (
        Index("uq_instruments_symbol_exchange", "canonical_symbol", "exchange", unique=True),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    canonical_symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    exchange: Mapped[str] = mapped_column(String(32), nullable=False, default="UNKNOWN")
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    sector: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    holdings: Mapped[list["Holding"]] = relationship(back_populates="instrument")
