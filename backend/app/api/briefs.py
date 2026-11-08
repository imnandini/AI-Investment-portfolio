from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.auth import CurrentUser, SessionDep
from app.core.config import Settings, get_settings
from app.services.research_briefs import holding_brief, portfolio_brief

router = APIRouter(prefix="/portfolios/{portfolio_id}", tags=["research briefs"])
Config = Annotated[Settings, Depends(get_settings)]


@router.post("/holdings/{holding_id}/brief")
async def stock(portfolio_id: UUID, holding_id: UUID, user: CurrentUser, session: SessionDep, settings: Config):
    return await holding_brief(session, settings, user.id, portfolio_id, holding_id)


@router.post("/brief")
async def portfolio(portfolio_id: UUID, user: CurrentUser, session: SessionDep, settings: Config):
    return await portfolio_brief(session, settings, user.id, portfolio_id)
