from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from app.analytics.portfolio import calculate_portfolio_analytics
from app.api.auth import CurrentUser
from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.models.review import ChatMessage
from app.rag.retrieval import retrieve
from app.schemas.research import SearchRequest
from app.services.prices import require_portfolio, saved_prices
from app.services.indmoney import list_balances
from app.services.portfolio_chat import answer_question, named_holdings
from app.services.daily_prices import ensure_daily_prices

router = APIRouter(prefix="/portfolios/{portfolio_id}/chat", tags=["research chat"])
DB = Annotated[Session, Depends(get_session)]


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    question: str = Field(min_length=2, max_length=1000)


@router.post("")
async def ask(portfolio_id: UUID, payload: ChatRequest, session: DB, user: CurrentUser, settings: Annotated[Settings, Depends(get_settings)]):
    portfolio = require_portfolio(session, user.id, portfolio_id)
    await ensure_daily_prices(session, portfolio, settings)
    metrics = calculate_portfolio_analytics(portfolio, saved_prices(session, portfolio_id))
    balances = list_balances(session, user.id, portfolio_id)
    selected = named_holdings(payload.question, portfolio.holdings)
    companies = sorted({h.instrument.canonical_symbol for h in (selected or portfolio.holdings)} | (set() if selected else {b["symbol"] for b in balances}))
    evidence = []
    document_issue = None
    try:
        # SearchRequest bounds each company filter to 50. Search every batch so
        # larger imported portfolios retain document coverage.
        for start in range(0, len(companies), 50):
            evidence.extend(retrieve(session, user.id, SearchRequest(query=payload.question, companies=companies[start:start + 50], limit=4), settings))
        evidence = sorted(evidence, key=lambda item: item.score, reverse=True)[:4]
    except Exception:
        document_issue = "Your document library could not be searched. Portfolio calculations and public news remain available."
    response = await answer_question(session, settings, user.id, portfolio, metrics, payload.question, evidence)
    if document_issue:
        response["limitations"].append(document_issue)
    if balances:
        response["limitations"].append("PF balances are shown separately from security cost basis, valuations and allocation metrics.")
    response["portfolio_context"] = {"name": portfolio.name, "position_count": len(portfolio.holdings), "cost_basis": str(metrics.cost_basis_total) if metrics.cost_basis_total is not None else None, "currency": portfolio.base_currency, "price_coverage": f"{metrics.priced_position_count}/{len(portfolio.holdings)}", "complete": metrics.complete}
    response["activities"].append("Searched optional documents tagged to your portfolio companies" if companies else "No saved company tags to search in the document library")
    message = ChatMessage(user_id=user.id, portfolio_id=portfolio_id, question=payload.question, response=response)
    session.add(message)
    session.commit()
    return {"id": message.id, "question": message.question, "created_at": message.created_at, "response": response}


@router.get("")
def history(portfolio_id: UUID, session: DB, user: CurrentUser):
    require_portfolio(session, user.id, portfolio_id)
    rows = list(session.scalars(select(ChatMessage).where(ChatMessage.user_id == user.id, ChatMessage.portfolio_id == portfolio_id).order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc()).limit(50)))
    return [{"id": row.id, "question": row.question, "response": row.response, "created_at": row.created_at} for row in reversed(rows)]


@router.delete("", status_code=204)
def clear_history(portfolio_id: UUID, session: DB, user: CurrentUser):
    require_portfolio(session, user.id, portfolio_id)
    session.execute(delete(ChatMessage).where(ChatMessage.user_id == user.id, ChatMessage.portfolio_id == portfolio_id))
    session.commit()
