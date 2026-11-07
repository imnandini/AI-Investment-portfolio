from app.core.config import Settings
from app.models.document_chunk import DocumentChunk
from app.rag.embeddings import create_embeddings
from ingestion.chunker import chunk_pages


def index_pages(session, document, pages, settings: Settings):
    provider = create_embeddings(settings)
    for page, ordinal, text in chunk_pages(pages, settings.chunk_size, settings.chunk_overlap):
        session.add(DocumentChunk(
            document_id=document.id, page=page, ordinal=ordinal, text=text,
            embedding=provider.embed(text) if provider else None,
            embedding_model=provider.model if provider else None,
        ))
    session.flush()
