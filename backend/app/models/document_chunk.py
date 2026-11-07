from uuid import UUID, uuid4
from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Index, Integer, JSON, String, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        Index("ix_chunks_keyword", text("to_tsvector('english', text)"), postgresql_using="gin").ddl_if(dialect="postgresql"),
        Index("ix_chunks_vector", "embedding", postgresql_using="hnsw", postgresql_ops={"embedding": "vector_cosine_ops"}).ddl_if(dialect="postgresql"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    page: Mapped[int] = mapped_column(Integer)
    ordinal: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list | None] = mapped_column(Vector(384).with_variant(JSON(), "sqlite"))
    embedding_model: Mapped[str | None] = mapped_column(String(200))
    document: Mapped["Document"] = relationship(back_populates="chunks")
