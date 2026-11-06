from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from app.api.auth import CurrentUser
from app.core.config import Settings, get_settings
from app.schemas.financial_data import CompanyProfile, PriceQuote, ProviderResult
from app.services.financial_data import create_financial_data_service


router = APIRouter(prefix="/financial-data", tags=["financial data"])
ExchangeQuery = Annotated[str, Query(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")]
SymbolPath = Annotated[str, Path(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9._-]+$")]


@router.get("/profile/{symbol}", response_model=ProviderResult[CompanyProfile])
async def read_company_profile(
    symbol: SymbolPath,
    exchange: ExchangeQuery,
    _current_user: CurrentUser,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ProviderResult[CompanyProfile]:
    service = create_financial_data_service(settings)
    return await service.get_company_profile(symbol, exchange)


@router.get("/price/{symbol}", response_model=ProviderResult[PriceQuote])
async def read_price(
    symbol: SymbolPath,
    exchange: ExchangeQuery,
    _current_user: CurrentUser,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ProviderResult[PriceQuote]:
    service = create_financial_data_service(settings)
    return await service.get_price(symbol, exchange)
