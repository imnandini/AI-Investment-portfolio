from app.schemas.financial_data import CompanyProfile, PriceQuote, ProviderIssue, ProviderResult


class UnavailableFinancialDataProvider:
    """Fail-closed adapter used while no licensed provider is configured."""

    name = "none"

    def __init__(self, code: str = "provider_not_configured") -> None:
        if code not in {"provider_not_configured", "provider_not_implemented"}:
            raise ValueError("Unsupported unavailable-provider code.")
        self.code = code

    async def get_company_profile(self, symbol: str, exchange: str) -> ProviderResult[CompanyProfile]:
        return ProviderResult[CompanyProfile](
            status="unavailable",
            issue=self._issue("company profile"),
        )

    async def get_price(self, symbol: str, exchange: str) -> ProviderResult[PriceQuote]:
        return ProviderResult[PriceQuote](
            status="unavailable",
            issue=self._issue("market price"),
        )

    def _issue(self, data_kind: str) -> ProviderIssue:
        if self.code == "provider_not_implemented":
            message = f"The configured financial data provider cannot be used; {data_kind} lookup is disabled."
        else:
            message = f"No authorized financial data provider is configured; {data_kind} lookup is unavailable."
        return ProviderIssue(code=self.code, message=message, retryable=False)
