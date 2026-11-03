from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.auth import CurrentUser
from app.db.session import get_session
from app.schemas.portfolio import PortfolioCreate, PortfolioDetail, PortfolioRead, PortfolioUpdate
from app.services.portfolios import PortfolioNotFoundError
from app.services.portfolios import (
    create_portfolio,
    delete_portfolio,
    get_portfolio,
    list_portfolios,
    update_portfolio,
)


router = APIRouter(prefix="/portfolios", tags=["portfolios"])
SessionDep = Annotated[Session, Depends(get_session)]


@router.post("", response_model=PortfolioRead, status_code=status.HTTP_201_CREATED)
def create(
    payload: PortfolioCreate, session: SessionDep, current_user: CurrentUser
) -> PortfolioRead:
    return create_portfolio(session, current_user.id, payload)


@router.get("", response_model=list[PortfolioRead])
def list_mine(session: SessionDep, current_user: CurrentUser) -> list[PortfolioRead]:
    return list_portfolios(session, current_user.id)


@router.get("/{portfolio_id}", response_model=PortfolioDetail)
def read_one(
    portfolio_id: UUID, session: SessionDep, current_user: CurrentUser
) -> PortfolioDetail:
    try:
        return get_portfolio(session, current_user.id, portfolio_id)
    except PortfolioNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found.") from None


@router.patch("/{portfolio_id}", response_model=PortfolioRead)
def update(
    portfolio_id: UUID,
    payload: PortfolioUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> PortfolioRead:
    try:
        return update_portfolio(session, current_user.id, portfolio_id, payload)
    except PortfolioNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found.") from None


@router.delete("/{portfolio_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(
    portfolio_id: UUID, session: SessionDep, current_user: CurrentUser
) -> Response:
    try:
        delete_portfolio(session, current_user.id, portfolio_id)
    except PortfolioNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found.") from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)
