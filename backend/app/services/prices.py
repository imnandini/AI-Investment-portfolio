from sqlalchemy import select
from fastapi import HTTPException
from app.analytics.models import PriceInput
from app.models.data_source import ManualPrice
from app.services.portfolios import PortfolioNotFoundError, get_portfolio


def require_portfolio(session, user_id, portfolio_id):
    try:
        return get_portfolio(session, user_id, portfolio_id)
    except PortfolioNotFoundError:
        raise HTTPException(404, "Portfolio not found.") from None


def saved_prices(session, portfolio_id):
    return [PriceInput.model_validate(row.payload) for row in session.scalars(select(ManualPrice).where(ManualPrice.portfolio_id == portfolio_id))]
