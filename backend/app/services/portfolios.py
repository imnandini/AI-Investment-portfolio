from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.holding import Holding
from app.models.instrument import Instrument
from app.models.portfolio import Portfolio
from app.schemas.portfolio import HoldingCreate, HoldingUpdate, PortfolioCreate, PortfolioUpdate


class PortfolioNotFoundError(Exception):
    pass


class HoldingNotFoundError(Exception):
    pass


class PortfolioConflictError(Exception):
    pass


def list_portfolios(session: Session, user_id: UUID) -> list[Portfolio]:
    statement = select(Portfolio).where(Portfolio.user_id == user_id).order_by(Portfolio.created_at)
    return list(session.scalars(statement))


def create_portfolio(session: Session, user_id: UUID, data: PortfolioCreate) -> Portfolio:
    portfolio = Portfolio(user_id=user_id, **data.model_dump())
    session.add(portfolio)
    session.commit()
    session.refresh(portfolio)
    return portfolio


def get_portfolio(session: Session, user_id: UUID, portfolio_id: UUID) -> Portfolio:
    statement = (
        select(Portfolio)
        .where(Portfolio.id == portfolio_id, Portfolio.user_id == user_id)
        .options(selectinload(Portfolio.holdings).selectinload(Holding.instrument))
        .execution_options(populate_existing=True)
    )
    portfolio = session.scalar(statement)
    if portfolio is None:
        raise PortfolioNotFoundError
    return portfolio


def update_portfolio(
    session: Session, user_id: UUID, portfolio_id: UUID, data: PortfolioUpdate
) -> Portfolio:
    portfolio = get_portfolio(session, user_id, portfolio_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(portfolio, field, value)
    session.commit()
    session.refresh(portfolio)
    return portfolio


def delete_portfolio(session: Session, user_id: UUID, portfolio_id: UUID) -> None:
    portfolio = get_portfolio(session, user_id, portfolio_id)
    session.delete(portfolio)
    session.commit()


def list_holdings(session: Session, user_id: UUID, portfolio_id: UUID) -> list[Holding]:
    get_portfolio(session, user_id, portfolio_id)
    statement = (
        select(Holding)
        .join(Portfolio, Holding.portfolio_id == Portfolio.id)
        .join(Instrument, Holding.instrument_id == Instrument.id)
        .where(Portfolio.id == portfolio_id, Portfolio.user_id == user_id)
        .options(selectinload(Holding.instrument))
        .order_by(Instrument.canonical_symbol)
    )
    return list(session.scalars(statement))


def add_holding(
    session: Session, user_id: UUID, portfolio_id: UUID, data: HoldingCreate
) -> Holding:
    get_portfolio(session, user_id, portfolio_id)
    exchange = data.exchange or "UNKNOWN"
    instrument = session.scalar(
        select(Instrument).where(
            Instrument.canonical_symbol == data.symbol,
            Instrument.exchange == exchange,
        )
    )
    if instrument is None:
        instrument = Instrument(
            canonical_symbol=data.symbol,
            exchange=exchange,
            asset_type=data.asset_type,
            currency=data.currency,
            sector=data.sector,
        )
        session.add(instrument)
        session.flush()
    elif instrument.asset_type != data.asset_type or instrument.currency != data.currency:
        raise PortfolioConflictError("The symbol already exists with different instrument details.")
    elif data.sector and instrument.sector and instrument.sector != data.sector:
        raise PortfolioConflictError("The symbol already exists with a different sector.")
    elif data.sector and instrument.sector is None:
        instrument.sector = data.sector

    holding = Holding(
        portfolio_id=portfolio_id,
        instrument_id=instrument.id,
        quantity=data.quantity,
        average_cost=data.average_cost,
        purchase_date=data.purchase_date,
    )
    session.add(holding)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise PortfolioConflictError("This instrument is already in the portfolio.") from exc
    return session.scalar(
        select(Holding).where(Holding.id == holding.id).options(selectinload(Holding.instrument))
    )


def update_holding(
    session: Session,
    user_id: UUID,
    portfolio_id: UUID,
    holding_id: UUID,
    data: HoldingUpdate,
) -> Holding:
    get_portfolio(session, user_id, portfolio_id)
    statement = (
        select(Holding)
        .join(Portfolio, Holding.portfolio_id == Portfolio.id)
        .where(
            Holding.id == holding_id,
            Holding.portfolio_id == portfolio_id,
            Portfolio.user_id == user_id,
        )
        .options(selectinload(Holding.instrument))
    )
    holding = session.scalar(statement)
    if holding is None:
        raise HoldingNotFoundError
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(holding, field, value)
    session.commit()
    session.refresh(holding)
    return holding


def delete_holding(
    session: Session, user_id: UUID, portfolio_id: UUID, holding_id: UUID
) -> None:
    get_portfolio(session, user_id, portfolio_id)
    statement = (
        select(Holding)
        .join(Portfolio, Holding.portfolio_id == Portfolio.id)
        .where(
            Holding.id == holding_id,
            Holding.portfolio_id == portfolio_id,
            Portfolio.user_id == user_id,
        )
    )
    holding = session.scalar(statement)
    if holding is None:
        raise HoldingNotFoundError
    session.delete(holding)
    session.commit()
