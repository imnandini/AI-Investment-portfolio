"""Create the initial user, portfolio, instrument, and holding schema."""
from alembic import op
import sqlalchemy as sa


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "instruments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("canonical_symbol", sa.String(length=32), nullable=False),
        sa.Column("exchange", sa.String(length=32), nullable=False),
        sa.Column("asset_type", sa.String(length=32), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_instruments"),
    )
    op.create_index(
        "uq_instruments_symbol_exchange",
        "instruments",
        ["canonical_symbol", "exchange"],
        unique=True,
    )

    op.create_table(
        "portfolios",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("base_currency", sa.String(length=3), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_portfolios_user_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_portfolios"),
    )
    op.create_index("ix_portfolios_user_id_created_at", "portfolios", ["user_id", "created_at"])

    op.create_table(
        "holdings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("portfolio_id", sa.Uuid(), nullable=False),
        sa.Column("instrument_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=24, scale=10), nullable=False),
        sa.Column("average_cost", sa.Numeric(precision=24, scale=10), nullable=False),
        sa.Column("purchase_date", sa.Date(), nullable=True),
        sa.CheckConstraint("average_cost >= 0", name="ck_holdings_average_cost_nonnegative"),
        sa.CheckConstraint("quantity > 0", name="ck_holdings_quantity_positive"),
        sa.ForeignKeyConstraint(
            ["instrument_id"], ["instruments.id"], name="fk_holdings_instrument_id_instruments", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["portfolio_id"], ["portfolios.id"], name="fk_holdings_portfolio_id_portfolios", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_holdings"),
    )
    op.create_index("ix_holdings_instrument_id", "holdings", ["instrument_id"])
    op.create_index("uq_holdings_portfolio_instrument", "holdings", ["portfolio_id", "instrument_id"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_holdings_portfolio_instrument", table_name="holdings")
    op.drop_index("ix_holdings_instrument_id", table_name="holdings")
    op.drop_table("holdings")
    op.drop_index("ix_portfolios_user_id_created_at", table_name="portfolios")
    op.drop_table("portfolios")
    op.drop_index("uq_instruments_symbol_exchange", table_name="instruments")
    op.drop_table("instruments")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
