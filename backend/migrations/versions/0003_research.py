"""Research corpus, cached provenance, manual prices and saved reviews/chat."""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "0003_research"
down_revision = "0002_instrument_sector"
branch_labels = None
depends_on = None

TABLES = ("data_source_records", "manual_prices", "documents", "document_chunks", "portfolio_reviews", "chat_messages")


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table("data_source_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("exchange", sa.String(32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("provider", "kind", "symbol", "exchange"))
    op.create_table("manual_prices",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("portfolio_id", sa.Uuid(), sa.ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("exchange", sa.String(32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.UniqueConstraint("portfolio_id", "symbol", "exchange"))
    op.create_index("ix_manual_prices_portfolio_id", "manual_prices", ["portfolio_id"])
    op.create_table("documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("company", sa.String(32), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("period", sa.String(40)),
        sa.Column("publication_date", sa.Date()),
        sa.Column("source_url", sa.String(1000)),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("error", sa.String(240)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "content_hash"))
    op.create_index("ix_documents_user_id", "documents", ["user_id"])
    op.create_index("ix_documents_company", "documents", ["company"])
    op.create_table("document_chunks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("document_id", sa.Uuid(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", sa.JSON().with_variant(Vector(384), "postgresql")),
        sa.Column("embedding_model", sa.String(200)))
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])
    op.create_table("portfolio_reviews",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("portfolio_id", sa.Uuid(), sa.ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("report", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_table("chat_messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("portfolio_id", sa.Uuid(), sa.ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question", sa.String(2000), nullable=False),
        sa.Column("response", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    for table in ("portfolio_reviews", "chat_messages"):
        for column in ("user_id", "portfolio_id"):
            op.create_index(f"ix_{table}_{column}", table, [column])
    if bind.dialect.name == "postgresql":
        op.execute("CREATE INDEX ix_chunks_keyword ON document_chunks USING gin (to_tsvector('english', text))")
        op.execute("CREATE INDEX ix_chunks_vector ON document_chunks USING hnsw (embedding vector_cosine_ops)")


def downgrade():
    for name in reversed(TABLES):
        op.drop_table(name)
