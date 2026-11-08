from typing import Annotated
from uuid import UUID
import asyncio

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete

from app.api.auth import CurrentUser, SessionDep
from app.core.config import Settings, get_settings
from app.integrations import indmoney as provider
from app.models.indmoney import IndmoneyConnection, IndmoneyPreview
from app.services import indmoney as imports
from app.services.prices import require_portfolio

router = APIRouter(prefix="/integrations/indmoney", tags=["INDmoney holdings"])
Config = Annotated[Settings, Depends(get_settings)]

# These sync endpoints run in FastAPI's worker pool: synchronous SQLAlchemy row
# locks must not block the event loop while another request awaits vendor I/O.


class CallbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=1, max_length=4096)
    state: str = Field(min_length=20, max_length=256)


class PreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    asset_type: str = Field(min_length=1, max_length=64)


class ImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preview_id: UUID


def fail(error):
    raise HTTPException(error.status, str(error)) from None


@router.get("")
def status(user: CurrentUser, session: SessionDep, settings: Config):
    connection = session.get(IndmoneyConnection, user.id)
    return {"configured": bool(settings.indmoney_token_key), "connected": bool(connection and connection.credentials),
            "connected_at": connection.connected_at if connection else None,
            "last_sync_at": connection.last_sync_at if connection else None}


@router.post("/connect")
def connect(user: CurrentUser, session: SessionDep, settings: Config):
    try:
        return asyncio.run(provider.begin_connection(session, user.id, settings))
    except provider.IndmoneyError as error:
        fail(error)


@router.post("/callback")
def callback(payload: CallbackRequest, user: CurrentUser, session: SessionDep, settings: Config):
    try:
        asyncio.run(provider.finish_connection(session, user.id, settings, payload.code, payload.state))
        return {"connected": True}
    except provider.IndmoneyError as error:
        fail(error)


@router.delete("", status_code=204)
def disconnect(user: CurrentUser, session: SessionDep):
    # Local credentials and pending imports are erased. Existing holdings are retained.
    session.execute(delete(IndmoneyPreview).where(IndmoneyPreview.user_id == user.id))
    session.execute(delete(IndmoneyConnection).where(IndmoneyConnection.user_id == user.id))
    session.commit()


@router.get("/assets")
def assets(user: CurrentUser, session: SessionDep, settings: Config):
    try:
        token = asyncio.run(provider.access_token(session, user.id, settings))
        return asyncio.run(provider.read_holdings(token))
    except provider.IndmoneyError as error:
        fail(error)


@router.post("/portfolios/{portfolio_id}/preview")
def preview(portfolio_id: UUID, payload: PreviewRequest, user: CurrentUser, session: SessionDep, settings: Config):
    require_portfolio(session, user.id, portfolio_id)
    try:
        token = asyncio.run(provider.access_token(session, user.id, settings))
        snapshot = asyncio.run(provider.read_holdings(token, payload.asset_type))
        return imports.preview_import(session, user.id, portfolio_id, settings, snapshot, payload.asset_type)
    except provider.IndmoneyError as error:
        fail(error)


@router.get("/portfolios/{portfolio_id}/balances")
def balances(portfolio_id: UUID, user: CurrentUser, session: SessionDep):
    return imports.list_balances(session, user.id, portfolio_id)


@router.post("/portfolios/{portfolio_id}/sync")
def sync(portfolio_id: UUID, payload: ImportRequest, user: CurrentUser, session: SessionDep, settings: Config):
    try:
        return imports.apply_import(session, user.id, portfolio_id, payload.preview_id, settings)
    except provider.IndmoneyError as error:
        session.rollback()
        fail(error)
