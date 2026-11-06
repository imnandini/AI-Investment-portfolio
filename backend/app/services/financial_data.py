import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

from app.core.config import Settings
from app.integrations.financial_data.base import FinancialDataProvider, ProviderError
from app.integrations.financial_data.unavailable import UnavailableFinancialDataProvider
from app.schemas.financial_data import (
    CompanyProfile,
    PriceQuote,
    ProviderIssue,
    ProviderResult,
)


_SAFE_MESSAGES = {
    "not_found": "The provider has no matching instrument or profile.",
    "rate_limited": "The provider rate limit was reached; try again later.",
    "authentication_failed": "The provider credentials are unavailable or were rejected.",
    "invalid_response": "The provider returned data that could not be validated.",
    "provider_error": "The provider could not complete the request.",
}
T = TypeVar("T")


class FinancialDataService:
    """Apply bounded timeouts and stable failure states around provider adapters."""

    def __init__(self, provider: FinancialDataProvider, timeout_seconds: float = 5.0) -> None:
        if timeout_seconds <= 0:
            raise ValueError("Provider timeout must be positive.")
        self.provider = provider
        self.timeout_seconds = timeout_seconds

    async def get_company_profile(self, symbol: str, exchange: str) -> ProviderResult[CompanyProfile]:
        return await self._call(self.provider.get_company_profile, symbol, exchange)

    async def get_price(self, symbol: str, exchange: str) -> ProviderResult[PriceQuote]:
        return await self._call(self.provider.get_price, symbol, exchange)

    async def _call(
        self,
        method: Callable[[str, str], Awaitable[ProviderResult[T]]],
        symbol: str,
        exchange: str,
    ) -> ProviderResult[T]:
        try:
            return await asyncio.wait_for(
                method(symbol, exchange),
                timeout=self.timeout_seconds,
            )
        except asyncio.TimeoutError:
            return ProviderResult[T](
                status="unavailable",
                issue=ProviderIssue(
                    code="timeout",
                    message="The financial data provider did not respond before the timeout.",
                    retryable=True,
                ),
            )
        except ProviderError as exc:
            return ProviderResult[T](
                status="unavailable",
                issue=ProviderIssue(
                    code=exc.code,
                    message=_SAFE_MESSAGES[exc.code],
                    retryable=exc.retryable,
                ),
            )
        except Exception:
            return ProviderResult[T](
                status="unavailable",
                issue=ProviderIssue(
                    code="provider_error",
                    message=_SAFE_MESSAGES["provider_error"],
                    retryable=True,
                ),
            )


def create_financial_data_service(settings: Settings) -> FinancialDataService:
    """Build only an approved adapter; unknown or unimplemented providers fail closed."""
    provider_name = settings.financial_data_provider.strip().lower()
    if provider_name == "none":
        provider: FinancialDataProvider = UnavailableFinancialDataProvider()
    else:
        provider = UnavailableFinancialDataProvider("provider_not_implemented")
    return FinancialDataService(provider, settings.financial_data_timeout_seconds)
