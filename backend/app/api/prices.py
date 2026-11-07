from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from app.analytics.models import PriceInput
from app.api.auth import CurrentUser
from app.db.session import get_session
from app.models.data_source import ManualPrice
from app.services.prices import require_portfolio, saved_prices

router = APIRouter(prefix="/portfolios/{portfolio_id}/prices", tags=["manual prices"])
DB = Annotated[Session, Depends(get_session)]


@router.get("", response_model=list[PriceInput])
def list_prices(portfolio_id: UUID, session: DB, user: CurrentUser):
    require_portfolio(session, user.id, portfolio_id)
    return saved_prices(session, portfolio_id)


@router.put("", response_model=PriceInput)
def save_price(portfolio_id: UUID, payload: PriceInput, session: DB, user: CurrentUser):
    portfolio = require_portfolio(session, user.id, portfolio_id)
    if payload.as_of and payload.as_of > datetime.now(timezone.utc) + timedelta(minutes=5):
        raise HTTPException(422, "Price as-of cannot be in the future.")
    if not any((h.instrument.canonical_symbol, h.instrument.exchange) == (payload.symbol, payload.exchange) for h in portfolio.holdings):
        raise HTTPException(422, "Price must match a holding's symbol and exchange.")
    row = session.scalar(select(ManualPrice).where(ManualPrice.portfolio_id == portfolio_id, ManualPrice.symbol == payload.symbol, ManualPrice.exchange == payload.exchange))
    if row is None:
        row = ManualPrice(portfolio_id=portfolio_id, symbol=payload.symbol, exchange=payload.exchange)
        session.add(row)
    row.payload = payload.model_dump(mode="json")
    session.commit()
    return payload


@router.delete("", status_code=204)
def clear_prices(portfolio_id: UUID, session: DB, user: CurrentUser):
    require_portfolio(session, user.id, portfolio_id)
    session.execute(delete(ManualPrice).where(ManualPrice.portfolio_id == portfolio_id))
    session.commit()
