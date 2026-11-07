import hashlib
from uuid import UUID
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.review import ChatMessage, PortfolioReview
from app.rag.indexing import index_pages
from ingestion.pdf_loader import PDFError, extract_pages


def ingest_document(session, user_id, content, metadata, settings):
    digest = hashlib.sha256(content).hexdigest()
    if session.scalar(select(Document).where(Document.user_id == user_id, Document.content_hash == digest)):
        raise HTTPException(409, "This PDF is already in your library. Delete its existing record to retry.")
    values = metadata.model_dump()
    values["source_url"] = str(metadata.source_url) if metadata.source_url else None
    document = Document(user_id=user_id, content_hash=digest, **values)
    session.add(document)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "This PDF is already in your library.") from None
    try:
        pages = extract_pages(content)
        document.page_count = len(pages)
        # A savepoint prevents partial chunks surviving an index/embedding failure.
        with session.begin_nested():
            index_pages(session, document, pages, settings)
        document.status = "ready"
    except PDFError as exc:
        document.status = exc.code
        document.error = str(exc)
    except Exception:
        document.status = "index_error"
        document.error = "Indexing failed. Check the embedding model configuration, then retry indexing."
    session.commit()
    session.refresh(document)
    return document


def owned_document(session, user_id, document_id):
    doc = session.scalar(select(Document).where(Document.id == document_id, Document.user_id == user_id))
    if not doc:
        raise HTTPException(404, "Document not found.")
    return doc


def erase_document(session, user_id, document_id):
    doc = owned_document(session, user_id, document_id)
    # Saved excerpts must not preserve deleted document content.
    session.execute(delete(ChatMessage).where(ChatMessage.user_id == user_id))
    session.execute(delete(PortfolioReview).where(PortfolioReview.user_id == user_id))
    session.delete(doc)
    session.commit()
