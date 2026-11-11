from sqlalchemy import select, func, and_
import json
from datetime import datetime, time, timedelta, timezone
from fastapi import HTTPException
from app.analytics.models import PriceInput
from app.models.data_source import ManualPrice
from app.models.indmoney import IndmoneyPrice
from app.models.daily_price import DailyPrice
from app.models.holding import Holding
from app.services.portfolios import PortfolioNotFoundError, get_portfolio


def require_portfolio(session, user_id, portfolio_id):
    try:
        return get_portfolio(session, user_id, portfolio_id)
    except PortfolioNotFoundError:
        raise HTTPException(404, "Portfolio not found.") from None


def saved_prices(session, portfolio_id):
    quotes = {(row.symbol, row.exchange): PriceInput.model_validate(json.loads(row.payload)).model_copy(update={"source": "INDmoney"})
              for row in session.scalars(select(IndmoneyPrice).where(IndmoneyPrice.portfolio_id == portfolio_id))}
    for row in session.scalars(select(ManualPrice).where(ManualPrice.portfolio_id == portfolio_id)):
        manual = PriceInput.model_validate(row.payload).model_copy(update={"source": "Manual reference"})
        previous = quotes.get((row.symbol, row.exchange))
        if previous and previous.as_of and (manual.as_of is None or previous.as_of > manual.as_of):
            continue
        quotes[(row.symbol, row.exchange)] = manual
    # Only load the latest close per instrument, rather than rereading the full
    # retained history for every valuation. Prefer the newest dated source.
    ist = timezone(timedelta(hours=5, minutes=30))
    target = datetime.now(ist).date() - timedelta(days=1)
    latest = select(DailyPrice.instrument_id, func.max(DailyPrice.trade_date).label("day")).where(
        DailyPrice.trade_date <= target).group_by(DailyPrice.instrument_id).subquery()
    rows = session.execute(select(DailyPrice, Holding).join(latest, and_(DailyPrice.instrument_id == latest.c.instrument_id,
        DailyPrice.trade_date == latest.c.day)).join(Holding, Holding.instrument_id == DailyPrice.instrument_id)
        .where(Holding.portfolio_id == portfolio_id).execution_options(populate_existing=True)).all()
    for daily, holding in rows:
        if daily.trade_date >= datetime.now(ist).date() or daily.currency != holding.instrument.currency:
            continue
        key = (holding.instrument.canonical_symbol, holding.instrument.exchange)
        stamp = datetime.combine(daily.trade_date, time.min, ist)
        existing = quotes.get(key)
        if existing and existing.as_of and existing.as_of >= stamp:
            continue
        quotes[key] = PriceInput(symbol=key[0], exchange=key[1], currency=daily.currency, price=daily.close,
            as_of=stamp, source=daily.provider, kind="daily_close", source_exchange=daily.exchange)
    return list(quotes.values())
