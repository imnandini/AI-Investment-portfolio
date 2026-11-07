from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.auth import CurrentUser
from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.rag.embeddings import create_embeddings
from app.rag.retrieval import retrieve
from app.rag.answering import grounded_answer
from app.schemas.research import Answer, DocumentMetadata, DocumentRead, Evidence, SearchRequest
from app.services.documents import erase_document, ingest_document, owned_document
from ingestion.pdf_loader import MAX_BYTES

router = APIRouter(prefix="/documents", tags=["documents and research"])
DB = Annotated[Session, Depends(get_session)]
Config = Annotated[Settings, Depends(get_settings)]


@router.get("", response_model=list[DocumentRead])
def list_documents(session: DB, user: CurrentUser):
    return list(session.scalars(select(Document).where(Document.user_id == user.id).order_by(Document.created_at.desc()).limit(500)))


@router.post("", response_model=DocumentRead, status_code=201)
def upload_document(session: DB, user: CurrentUser, settings: Config,
                    file: Annotated[UploadFile, File()], metadata: Annotated[str, Form(max_length=3000)]):
    if file.content_type != "application/pdf":
        raise HTTPException(415, "Upload a PDF with application/pdf content type.")
    content = file.file.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise HTTPException(413, "PDF exceeds the 5 MB limit.")
    try:
        info = DocumentMetadata.model_validate_json(metadata)
    except ValidationError:
        raise HTTPException(422, "Invalid document metadata. Supply title, company and a supported document kind.") from None
    return ingest_document(session, user.id, content, info, settings)


@router.delete("/{document_id}", status_code=204)
def delete_document(document_id: UUID, session: DB, user: CurrentUser):
    erase_document(session, user.id, document_id)


@router.post("/{document_id}/reindex", response_model=DocumentRead)
def reindex_document(document_id: UUID, session: DB, user: CurrentUser, settings: Config):
    doc = owned_document(session, user.id, document_id)
    chunks = list(session.scalars(select(DocumentChunk).where(DocumentChunk.document_id == doc.id)))
    if not chunks:
        raise HTTPException(409, "No extracted chunks to reindex. Delete this record and upload the PDF again.")
    provider = create_embeddings(settings)
    try:
        for chunk in chunks:
            chunk.embedding = provider.embed(chunk.text) if provider else None
            chunk.embedding_model = provider.model if provider else None
        doc.status = "ready"
        doc.error = None
        session.commit()
    except Exception:
        session.rollback()
        raise HTTPException(503, "Embedding model unavailable. The previous index was retained.") from None
    return doc


@router.post("/search", response_model=list[Evidence])
def search_documents(payload: SearchRequest, session: DB, user: CurrentUser, settings: Config):
    return retrieve(session, user.id, payload, settings)


@router.post("/answer", response_model=Answer)
def answer_question(payload: SearchRequest, session: DB, user: CurrentUser, settings: Config):
    return grounded_answer(retrieve(session, user.id, payload, settings))
