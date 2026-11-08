"""Account-scoped OAuth credentials and short-lived, portfolio-bound import previews."""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class IndmoneyConnection(Base):
    __tablename__ = "indmoney_connections"
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    credentials: Mapped[str | None] = mapped_column(Text)
    pending: Mapped[str | None] = mapped_column(Text)
    state_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    state_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IndmoneyPreview(Base):
    __tablename__ = "indmoney_previews"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    portfolio_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("portfolios.id", ondelete="CASCADE"), index=True)
    payload: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class IndmoneyPrice(Base):
    __tablename__ = "indmoney_prices"
    portfolio_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("portfolios.id", ondelete="CASCADE"), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    exchange: Mapped[str] = mapped_column(String(32), primary_key=True)
    payload: Mapped[str] = mapped_column(Text)


class IndmoneyBalance(Base):
    """Non-traded accounts have reported balances, not security units or prices."""
    __tablename__ = "indmoney_balances"
    portfolio_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("portfolios.id", ondelete="CASCADE"), primary_key=True)
    asset_key: Mapped[str] = mapped_column(String(32), primary_key=True)
    payload: Mapped[str] = mapped_column(Text)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
