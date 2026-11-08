from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Holding(Base):
    __tablename__ = "holdings"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("average_cost >= 0", name="average_cost_nonnegative"),
        Index("uq_holdings_portfolio_instrument", "portfolio_id", "instrument_id", unique=True),
        Index("ix_holdings_instrument_id", "instrument_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    portfolio_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False
    )
    instrument_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("instruments.id", ondelete="RESTRICT"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    average_cost: Mapped[Decimal | None] = mapped_column(Numeric(24, 10), nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="manual", server_default="manual")
    purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    portfolio: Mapped["Portfolio"] = relationship(back_populates="holdings")
    instrument: Mapped["Instrument"] = relationship(back_populates="holdings")
