from typing import Annotated
from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.auth import CurrentUser
from app.api.financial_data import ExchangeQuery, SymbolPath
from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.models.document import Document
from app.schemas.research import DocumentRead
from app.services.market_data import cached_lookup
from app.services.company_research import company_snapshot, search_companies
from app.schemas.company_research import CompanySearch, CompanySnapshot

router = APIRouter(prefix="/companies", tags=["company research"])


@router.get("/search", response_model=CompanySearch)
async def company_search(user: CurrentUser,
    settings: Annotated[Settings, Depends(get_settings)],
    q: Annotated[str, Query(min_length=2, max_length=200)]):
    return await search_companies(q, settings)


@router.get("/{symbol}/snapshot", response_model=CompanySnapshot)
async def read_company_snapshot(
    symbol: Annotated[str, Path(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9&._-]+$")],
    exchange: Annotated[str, Query(pattern=r"^(NSE|BSE)$")], user: CurrentUser,
    session: Annotated[Session, Depends(get_session)], settings: Annotated[Settings, Depends(get_settings)]):
    return await company_snapshot(session, settings, symbol, exchange)


@router.get("/{symbol}")
async def company_research(symbol: SymbolPath, exchange: ExchangeQuery, user: CurrentUser,
    session: Annotated[Session, Depends(get_session)], settings: Annotated[Settings, Depends(get_settings)]):
    profile = await cached_lookup(session, settings, "profile", symbol, exchange)
    price = await cached_lookup(session, settings, "price", symbol, exchange)
    docs = list(session.scalars(select(Document).where(Document.user_id == user.id, Document.company == symbol.upper()).order_by(Document.created_at.desc()).limit(50)))
    return {"symbol": symbol.upper(), "exchange": exchange.upper(), "profile": profile, "price": price,
        "financial_trends": [], "trend_status": "unavailable", "trend_note": "No authorized statement provider is connected. Search your uploaded reports for period-specific figures.",
        "documents": [DocumentRead.model_validate(doc) for doc in docs]}
