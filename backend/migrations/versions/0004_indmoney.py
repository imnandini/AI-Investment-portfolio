"""INDmoney OAuth, previews, provenance, prices and unknown purchase costs."""
from alembic import op
import sqlalchemy as sa

revision = "0004_indmoney"
down_revision = "0003_research"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("indmoney_connections",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("credentials", sa.Text()), sa.Column("pending", sa.Text()),
        sa.Column("state_hash", sa.String(64), unique=True),
        sa.Column("state_expires_at", sa.DateTime(timezone=True)),
        sa.Column("connected_at", sa.DateTime(timezone=True)),
        sa.Column("last_sync_at", sa.DateTime(timezone=True)))
    op.create_table("indmoney_previews",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("portfolio_id", sa.Uuid(), sa.ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False))
    for column in ("user_id", "portfolio_id"):
        op.create_index(f"ix_indmoney_previews_{column}", "indmoney_previews", [column])
    op.create_table("indmoney_prices",
        sa.Column("portfolio_id", sa.Uuid(), sa.ForeignKey("portfolios.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("symbol", sa.String(32), primary_key=True),
        sa.Column("exchange", sa.String(32), primary_key=True),
        sa.Column("payload", sa.Text(), nullable=False))
    with op.batch_alter_table("holdings") as batch:
        batch.alter_column("average_cost", existing_type=sa.Numeric(24, 10), nullable=True)
        batch.add_column(sa.Column("source", sa.String(20), nullable=False, server_default="manual"))


def downgrade():
    # Unknown purchase costs cannot be converted to zero. Refuse a lossy downgrade.
    if op.get_bind().execute(sa.text("SELECT count(*) FROM holdings WHERE average_cost IS NULL")).scalar():
        raise RuntimeError("Resolve holdings with unknown purchase costs before downgrading.")
    with op.batch_alter_table("holdings") as batch:
        batch.drop_column("source")
        batch.alter_column("average_cost", existing_type=sa.Numeric(24, 10), nullable=False)
    for table in ("indmoney_prices", "indmoney_previews", "indmoney_connections"):
        op.drop_table(table)
