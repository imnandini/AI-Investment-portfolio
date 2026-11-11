"""Require email verification for new and existing accounts."""
from alembic import op
import sqlalchemy as sa

revision = "0007_email_verification"
down_revision = "0006_daily_prices"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("verification_code_hash", sa.String(64)))
    op.add_column("users", sa.Column("verification_expires_at", sa.DateTime(timezone=True)))
    op.add_column("users", sa.Column("verification_sent_at", sa.DateTime(timezone=True)))
    op.add_column("users", sa.Column("verification_attempts", sa.Integer(), nullable=False, server_default="0"))


def downgrade():
    for column in ("verification_attempts", "verification_sent_at", "verification_expires_at", "verification_code_hash", "email_verified"):
        op.drop_column("users", column)
