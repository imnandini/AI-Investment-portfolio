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
from app.rag.answering import grounded_answer
from app.rag.retrieval import retrieve
from app.schemas.research import SearchRequest
from app.services.prices import require_portfolio, saved_prices
from app.services.indmoney import list_balances

router = APIRouter(prefix="/portfolios/{portfolio_id}/chat", tags=["research chat"])
DB = Annotated[Session, Depends(get_session)]


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    question: str = Field(min_length=2, max_length=1000)


@router.post("")
def ask(portfolio_id: UUID, payload: ChatRequest, session: DB, user: CurrentUser, settings: Annotated[Settings, Depends(get_settings)]):
    portfolio = require_portfolio(session, user.id, portfolio_id)
    metrics = calculate_portfolio_analytics(portfolio, saved_prices(session, portfolio_id))
    balances = list_balances(session, user.id, portfolio_id)
    companies = sorted({h.instrument.canonical_symbol for h in portfolio.holdings} | {b["symbol"] for b in balances})
    evidence = retrieve(session, user.id, SearchRequest(query=payload.question, companies=companies, limit=4), settings)
    response = grounded_answer(evidence).model_dump(mode="json")
    if balances:
        response["limitations"].append("PF balances are shown separately from security cost basis, valuations and allocation metrics.")
    response["portfolio_context"] = {"name": portfolio.name, "position_count": len(portfolio.holdings), "cost_basis": str(metrics.cost_basis_total) if metrics.cost_basis_total is not None else None, "currency": portfolio.base_currency, "price_coverage": f"{metrics.priced_position_count}/{len(portfolio.holdings)}", "complete": metrics.complete}
    response["activities"].insert(0, "Loaded your portfolio and calculated current metrics")
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
