from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.analytics.models import PortfolioAnalytics, PriceInput
from app.analytics.portfolio import calculate_portfolio_analytics
from app.api.auth import CurrentUser
from app.db.session import get_session
from app.services.portfolios import PortfolioNotFoundError, get_portfolio
from app.services.prices import saved_prices
from app.core.config import Settings, get_settings
from app.services.daily_prices import ensure_daily_prices, price_overview


router = APIRouter(prefix="/portfolios/{portfolio_id}/analytics", tags=["analytics"])
SessionDep = Annotated[Session, Depends(get_session)]


class AnalyticsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prices: list[PriceInput] = Field(default_factory=list)


@router.post("", response_model=PortfolioAnalytics)
async def read_analytics(
    portfolio_id: UUID,
    payload: AnalyticsRequest,
    session: SessionDep,
    current_user: CurrentUser,
    settings: Annotated[Settings, Depends(get_settings)],
) -> PortfolioAnalytics:
    try:
        portfolio = get_portfolio(session, current_user.id, portfolio_id)
    except PortfolioNotFoundError:
        raise HTTPException(status_code=404, detail="Portfolio not found.") from None

    holding_keys = {
        (holding.instrument.canonical_symbol.upper(), holding.instrument.exchange.upper())
        for holding in portfolio.holdings
    }
    supplied_keys = [(price.symbol, price.exchange) for price in payload.prices]
    if len(supplied_keys) != len(set(supplied_keys)):
        raise HTTPException(status_code=422, detail="Provide at most one price per symbol and exchange.")
    unknown = sorted(set(supplied_keys) - holding_keys)
    if unknown:
        raise HTTPException(status_code=422, detail="A supplied price does not match a holding in this portfolio.")
    try:
        await ensure_daily_prices(session, portfolio, settings)
        prices = {(p.symbol, p.exchange): p for p in saved_prices(session, portfolio_id)}
        prices.update({(p.symbol, p.exchange): p.model_copy(update={"source": "Supplied reference", "kind": "reference", "source_exchange": None}) for p in payload.prices})
        result = calculate_portfolio_analytics(portfolio, list(prices.values()))
        result.daily_prices = price_overview(session, portfolio, settings)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
