"""Dated daily closes and automatic refresh state."""
from alembic import op
import sqlalchemy as sa

revision = "0006_daily_prices"
down_revision = "0005_indmoney_names_balances"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("daily_prices",
        sa.Column("instrument_id", sa.Uuid(), sa.ForeignKey("instruments.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("trade_date", sa.Date(), primary_key=True),
        sa.Column("close", sa.Numeric(24, 10), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("provider_key", sa.String(160), nullable=False),
        sa.Column("exchange", sa.String(32), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("daily_price_sync",
        sa.Column("instrument_id", sa.Uuid(), sa.ForeignKey("instruments.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_check_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("requested_through", sa.Date(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("note", sa.String(300), nullable=False))


def downgrade():
    op.drop_table("daily_price_sync")
    op.drop_table("daily_prices")
