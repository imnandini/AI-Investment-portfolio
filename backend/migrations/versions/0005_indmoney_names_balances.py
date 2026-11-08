"""Company display names and non-traded INDmoney account balances."""
from alembic import op
import sqlalchemy as sa

revision = "0005_indmoney_names_balances"
down_revision = "0004_indmoney"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("instruments", sa.Column("display_name", sa.String(200), nullable=True))
    op.create_table("indmoney_balances",
        sa.Column("portfolio_id", sa.Uuid(), sa.ForeignKey("portfolios.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("asset_key", sa.String(32), primary_key=True),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False))


def downgrade():
    op.drop_table("indmoney_balances")
    op.drop_column("instruments", "display_name")
