from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.api.auth import CurrentUser
from app.db.session import get_session
from app.schemas.portfolio import HoldingCreate, HoldingRead, HoldingUpdate
from app.schemas.imports import HoldingsImportResponse
from app.services.csv_import import CsvImportFormatError, import_holdings_csv
from app.services.portfolios import (
    HoldingNotFoundError,
    PortfolioConflictError,
    PortfolioNotFoundError,
    add_holding,
    delete_holding,
    list_holdings,
    update_holding,
)


router = APIRouter(prefix="/portfolios/{portfolio_id}/holdings", tags=["holdings"])
SessionDep = Annotated[Session, Depends(get_session)]
MAX_UPLOAD_BYTES = 1_000_000


@router.post("/import", response_model=HoldingsImportResponse, status_code=status.HTTP_200_OK)
async def import_csv(
    portfolio_id: UUID,
    file: Annotated[UploadFile, File(description="UTF-8 CSV using the holdings template")],
    session: SessionDep,
    current_user: CurrentUser,
) -> HoldingsImportResponse:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=415, detail="Upload a .csv file.")
    if file.content_type not in {"text/csv", "application/csv", "application/vnd.ms-excel", "text/plain"}:
        raise HTTPException(status_code=415, detail="Upload a CSV file with a supported content type.")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="CSV file exceeds the 1 MB upload limit.")
    try:
        holdings, errors = import_holdings_csv(session, current_user.id, portfolio_id, content)
    except CsvImportFormatError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except PortfolioNotFoundError:
        raise HTTPException(status_code=404, detail="Portfolio not found.") from None
    return HoldingsImportResponse(imported_count=len(holdings), errors=errors, holdings=holdings)


@router.get("", response_model=list[HoldingRead])
def list_for_portfolio(
    portfolio_id: UUID, session: SessionDep, current_user: CurrentUser
) -> list[HoldingRead]:
    try:
        return list_holdings(session, current_user.id, portfolio_id)
    except PortfolioNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found.") from None


@router.post("", response_model=HoldingRead, status_code=status.HTTP_201_CREATED)
def create(
    portfolio_id: UUID,
    payload: HoldingCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> HoldingRead:
    try:
        return add_holding(session, current_user.id, portfolio_id, payload)
    except PortfolioNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found.") from None
    except PortfolioConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None


@router.patch("/{holding_id}", response_model=HoldingRead)
def update(
    portfolio_id: UUID,
    holding_id: UUID,
    payload: HoldingUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> HoldingRead:
    try:
        return update_holding(session, current_user.id, portfolio_id, holding_id, payload)
    except (PortfolioNotFoundError, HoldingNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holding not found.") from None


@router.delete("/{holding_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(
    portfolio_id: UUID,
    holding_id: UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> Response:
    try:
        delete_holding(session, current_user.id, portfolio_id, holding_id)
    except (PortfolioNotFoundError, HoldingNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holding not found.") from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)
