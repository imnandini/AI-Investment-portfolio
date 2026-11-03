"""Add optional sector metadata used by deterministic portfolio analytics."""
from alembic import op
import sqlalchemy as sa


revision = "0002_instrument_sector"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("instruments", sa.Column("sector", sa.String(length=80), nullable=True))


def downgrade() -> None:
    op.drop_column("instruments", "sector")
