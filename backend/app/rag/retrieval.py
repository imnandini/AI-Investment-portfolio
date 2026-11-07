from collections import Counter
import math
from uuid import UUID
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload
from app.core.config import Settings
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.rag.embeddings import create_embeddings, tokens
from app.rag.fusion import reciprocal_rank_fusion
from app.rag.reranker import rerank
from app.schemas.research import Evidence, SearchRequest


def lexical_score(query_tokens, text):
    counts = Counter(tokens(text))
    return sum(1 + math.log(counts[t]) for t in set(query_tokens) if counts[t]) / (1 + math.log(1 + sum(counts.values())))


def retrieve(session: Session, user_id: UUID, request: SearchRequest, settings: Settings) -> list[Evidence]:
    conditions = [Document.user_id == user_id, Document.status == "ready"]
    if request.company:
        conditions.append(Document.company == request.company.upper())
    if request.companies is not None:
        conditions.append(Document.company.in_([c.upper() for c in request.companies]))
    for field in ("kind", "period"):
        if getattr(request, field):
            conditions.append(getattr(Document, field) == getattr(request, field))
    if request.published_after:
        conditions.append(Document.publication_date >= request.published_after)
    if request.published_before:
        conditions.append(Document.publication_date <= request.published_before)
    if request.page:
        conditions.append(DocumentChunk.page == request.page)
    base = select(DocumentChunk).join(Document).where(*conditions).options(joinedload(DocumentChunk.document))
    query_tokens = tokens(request.query)
    if not query_tokens:
        return []
    provider = create_embeddings(settings)
    embedding = provider.embed(request.query) if provider else None
    if session.bind.dialect.name == "postgresql":
        vector = func.to_tsvector("english", DocumentChunk.text)
        query = func.plainto_tsquery("english", request.query)
        lexical = list(session.scalars(base.where(vector.op("@@")(query)).order_by(func.ts_rank_cd(vector, query).desc(), DocumentChunk.id).limit(40)))
        semantic = list(session.scalars(base.where(DocumentChunk.embedding_model == provider.model).order_by(DocumentChunk.embedding.cosine_distance(embedding), DocumentChunk.id).limit(40))) if provider else []
    else:
        # Portable reference implementation for SQLite tests/small local corpora.
        corpus = list(session.scalars(base.order_by(DocumentChunk.id).limit(5000)))
        lexical = sorted([c for c in corpus if lexical_score(query_tokens, c.text) > 0], key=lambda c: (-lexical_score(query_tokens, c.text), str(c.id)))[:40]
        semantic = sorted([c for c in corpus if provider and c.embedding_model == provider.model and c.embedding is not None and sum(a*b for a,b in zip(embedding, c.embedding)) > 0.05], key=lambda c: -sum(a*b for a,b in zip(embedding, c.embedding)))[:40]
    # Hash collisions alone do not constitute evidence. Semantic models may find synonyms.
    if not provider or provider.model.startswith("hash-"):
        semantic = [c for c in semantic if lexical_score(query_tokens, c.text) > 0]
    lookup = {c.id: c for c in lexical + semantic}
    fused = reciprocal_rank_fusion([[c.id for c in lexical], [c.id for c in semantic]])[:20]
    results = []
    for key, score in fused:
        chunk = lookup[key]
        doc = chunk.document
        results.append(Evidence(chunk_id=chunk.id, document_id=doc.id, title=doc.title, company=doc.company,
            page=chunk.page, period=doc.period, publication_date=doc.publication_date,
            source_url=doc.source_url, text=chunk.text, score=score))
    return rerank(request.query, results, settings.reranker_model_path)[:request.limit]
