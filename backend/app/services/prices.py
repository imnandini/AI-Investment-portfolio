from sqlalchemy import select
import json
from fastapi import HTTPException
from app.analytics.models import PriceInput
from app.models.data_source import ManualPrice
from app.models.indmoney import IndmoneyPrice
from app.services.portfolios import PortfolioNotFoundError, get_portfolio


def require_portfolio(session, user_id, portfolio_id):
    try:
        return get_portfolio(session, user_id, portfolio_id)
    except PortfolioNotFoundError:
        raise HTTPException(404, "Portfolio not found.") from None


def saved_prices(session, portfolio_id):
    quotes = {(row.symbol, row.exchange): PriceInput.model_validate(json.loads(row.payload))
              for row in session.scalars(select(IndmoneyPrice).where(IndmoneyPrice.portfolio_id == portfolio_id))}
    quotes.update({(row.symbol, row.exchange): PriceInput.model_validate(row.payload)
                   for row in session.scalars(select(ManualPrice).where(ManualPrice.portfolio_id == portfolio_id))})
    return list(quotes.values())
