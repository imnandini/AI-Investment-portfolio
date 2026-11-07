from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.auth import CurrentUser
from app.api.financial_data import ExchangeQuery, SymbolPath
from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.models.document import Document
from app.schemas.research import DocumentRead
from app.services.market_data import cached_lookup

router = APIRouter(prefix="/companies", tags=["company research"])


@router.get("/{symbol}")
async def company_research(symbol: SymbolPath, exchange: ExchangeQuery, user: CurrentUser,
    session: Annotated[Session, Depends(get_session)], settings: Annotated[Settings, Depends(get_settings)]):
    profile = await cached_lookup(session, settings, "profile", symbol, exchange)
    price = await cached_lookup(session, settings, "price", symbol, exchange)
    docs = list(session.scalars(select(Document).where(Document.user_id == user.id, Document.company == symbol.upper()).order_by(Document.created_at.desc()).limit(50)))
    return {"symbol": symbol.upper(), "exchange": exchange.upper(), "profile": profile, "price": price,
        "financial_trends": [], "trend_status": "unavailable", "trend_note": "No authorized statement provider is connected. Search your uploaded reports for period-specific figures.",
        "documents": [DocumentRead.model_validate(doc) for doc in docs]}
