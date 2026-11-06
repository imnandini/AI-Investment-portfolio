from typing import Literal, Protocol

from app.schemas.financial_data import CompanyProfile, PriceQuote, ProviderResult


ProviderErrorCode = Literal[
    "not_found",
    "rate_limited",
    "authentication_failed",
    "invalid_response",
    "provider_error",
]


class ProviderError(Exception):
    """A safe, normalized provider error; never include credentials in its message."""

    def __init__(self, code: ProviderErrorCode, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class FinancialDataProvider(Protocol):
    """Async read-only port implemented by each approved market data source."""

    name: str

    async def get_company_profile(self, symbol: str, exchange: str) -> ProviderResult[CompanyProfile]:
        """Return a sourced profile or a typed unavailable result."""

    async def get_price(self, symbol: str, exchange: str) -> ProviderResult[PriceQuote]:
        """Return a sourced quote or a typed unavailable result."""
