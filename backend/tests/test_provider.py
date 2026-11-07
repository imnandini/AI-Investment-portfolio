import asyncio
from datetime import datetime, timedelta, timezone
from app.schemas.financial_data import CompanyProfile, ProviderResult, SourceMetadata
from app.services.financial_data import FinancialDataService
from app.integrations.financial_data.base import ProviderError


def test_provider_timeout_and_error_are_bounded():
    class Slow:
        async def get_price(self, symbol, exchange):
            await asyncio.sleep(1)
    result = asyncio.run(FinancialDataService(Slow(), .01).get_price("AAA", "NSE"))
    assert result.issue.code == "timeout"
    class Broken:
        async def get_price(self, symbol, exchange):
            raise RuntimeError("secret token must not escape")
    result = asyncio.run(FinancialDataService(Broken()).get_price("AAA", "NSE"))
    assert "secret" not in result.model_dump_json()
    assert result.issue.code == "provider_error"


def test_expired_cache_is_not_returned_as_fresh(api_context, monkeypatch):
    from app.models.data_source import DataSourceRecord
    from app.services.market_data import cached_lookup
    from app.core.config import Settings
    _, _, _, _, session = api_context
    now = datetime.now(timezone.utc)
    old = ProviderResult[CompanyProfile](status="available", data=CompanyProfile(symbol="AAA", exchange="NSE", company_name="Old Co"), source=SourceMetadata(provider="none", retrieved_at=now - timedelta(days=1)))
    session.add(DataSourceRecord(provider="none", kind="profile", symbol="AAA", exchange="NSE", payload=old.model_dump(mode="json"), retrieved_at=now-timedelta(days=1), expires_at=now-timedelta(hours=1)))
    session.commit()
    result = asyncio.run(cached_lookup(session, Settings(), "profile", "AAA", "NSE"))
    assert result["result"].status == "unavailable"
    assert result["cache_status"] == "refreshed"


def test_quote_freshness_distinguishes_missing_date_and_stale_source():
    from app.schemas.financial_data import PriceQuote
    from app.services.market_data import freshness
    now = datetime.now(timezone.utc)
    result = ProviderResult[PriceQuote](status="available", data=PriceQuote(symbol="AAA", exchange="NSE", price="1", currency="INR"), source=SourceMetadata(provider="test", retrieved_at=now))
    assert freshness(result, "price", now) == "unknown_freshness"
    result.data.as_of = now - timedelta(days=10)
    assert freshness(result, "price", now) == "stale"
    result.data.as_of = now
    assert freshness(result, "price", now) == "available"
