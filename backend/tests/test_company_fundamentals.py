import asyncio
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from app.core.config import Settings
from app.integrations.company_fundamentals import CompanyResearchError, number, statement, yahoo_company_search, yahoo_company_snapshot
from app.models.data_source import DataSourceRecord
from app.services.company_research import company_snapshot


def test_search_returns_confirmable_indian_equities_only(monkeypatch):
    class Search:
        def __init__(self, query, **kwargs):
            assert query == "Aarti Industries"
            self.quotes = [
                {"symbol": "AARTIIND.NS", "quoteType": "EQUITY", "longname": "Aarti Industries Limited"},
                {"symbol": "AARTIIND.BO", "quoteType": "EQUITY", "shortname": "Aarti Industries"},
                {"symbol": "AARTIIND.NS", "quoteType": "EQUITY", "longname": "Aarti Industries Limited"},
                {"symbol": "AAPL", "quoteType": "EQUITY", "shortname": "Apple"},
                {"symbol": "FAKE.NS", "quoteType": "MUTUALFUND", "shortname": "Fund"},
            ]
    monkeypatch.setattr("yfinance.Search", Search)
    assert [(m.symbol, m.exchange) for m in yahoo_company_search("Aarti Industries")] == [("AARTIIND", "NSE"), ("AARTIIND", "BSE")]
    for internal in ["INDS00001", "INE769A01020", "EPF-012345", "  "]:
        with pytest.raises(CompanyResearchError):
            yahoo_company_search(internal)


def test_financials_preserve_unknowns_negative_cash_flow_and_periods():
    frame = pd.DataFrame({pd.Timestamp("2026-03-31"): [1e10, float("nan"), -200],
                          pd.Timestamp("2025-03-31"): [0, 2, float("inf")]},
                         index=["TotalRevenue", "DilutedEPS", "FreeCashFlow"])
    table = statement(frame, "Annual", "INR", [("Revenue", ["TotalRevenue"]), ("EPS", ["DilutedEPS"]),
        ("Cash flow", ["FreeCashFlow"]), ("Missing", ["NotSupplied"])])
    assert table.periods == ["2026-03-31", "2025-03-31"]
    assert table.rows[0].values == ["10000000000.0", "0.0"]
    assert table.rows[1].values == [None, "2.0"] and table.rows[1].unit == "per_share"
    assert table.rows[2].values == ["-200.0", None]
    assert table.rows[3].values == [None, None]
    assert number(float("nan")) is None and number(True) is None
    assert number("0.15", 100) == "15.00"


def test_snapshot_verifies_identity_currency_and_labels_metrics(monkeypatch):
    class Ticker:
        def __init__(self, symbol):
            assert symbol == "AARTIIND.NS"
        def get_info(self):
            return {"symbol": "AARTIIND.NS", "exchange": "NSI", "quoteType": "EQUITY", "currency": "INR",
                "financialCurrency": "INR", "longName": "Aarti Industries", "returnOnEquity": .07,
                "marketCap": 10000000000, "totalRevenue": 20000000000, "regularMarketTime": 1794560400}
        def get_income_stmt(self, **kwargs):
            return pd.DataFrame({pd.Timestamp("2026-03-31"): [20000000000]}, index=["TotalRevenue"])
        def get_balance_sheet(self):
            return pd.DataFrame()
        def get_cashflow(self):
            raise RuntimeError("upstream secret must not escape")
    monkeypatch.setattr("yfinance.Ticker", Ticker)
    result = yahoo_company_snapshot("AARTIIND", "NSE")
    assert next(m for m in result["metrics"] if m["label"] == "Return on equity")["value"] == "7.00"
    assert result["price"] is None
    assert len(result["statements"]) == 2
    assert "secret" not in str(result)
    original = Ticker.get_info
    monkeypatch.setattr(Ticker, "get_info", lambda self: {**original(self), "exchange": "BSE"})
    with pytest.raises(CompanyResearchError):
        yahoo_company_snapshot("AARTIIND", "NSE")
    monkeypatch.setattr(Ticker, "get_info", lambda self: {**original(self), "financialCurrency": "USD"})
    foreign = yahoo_company_snapshot("AARTIIND", "NSE")
    assert not foreign["statements"]
    assert next(m for m in foreign["metrics"] if m["label"] == "Revenue")["value"] is None


def test_snapshot_cache_and_failure_do_not_relabel_stale_success(api_context, monkeypatch):
    _, _, _, _, session = api_context
    settings = Settings(company_research_provider="yahoo")
    calls = []
    async def fetch(function, symbol, exchange):
        calls.append((symbol, exchange))
        return {"name": "Aarti Industries", "currency": "INR"}
    monkeypatch.setattr("app.services.company_research.provider_call", fetch)
    first = asyncio.run(company_snapshot(session, settings, "aartiind", "NSE"))
    second = asyncio.run(company_snapshot(session, settings, "AARTIIND", "NSE"))
    assert first.status == "available" and not first.cached and second.cached
    assert calls == [("AARTIIND", "NSE")]
    record = session.query(DataSourceRecord).filter_by(kind="fundamentals").one()
    record.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    session.commit()
    async def fail(*args):
        raise CompanyResearchError("Provider unavailable")
    monkeypatch.setattr("app.services.company_research.provider_call", fail)
    failed = asyncio.run(company_snapshot(session, settings, "AARTIIND", "NSE"))
    assert failed.status == "unavailable" and failed.name is None
    assert failed.notes == ["Provider unavailable"]
    assert asyncio.run(company_snapshot(session, settings, "AARTIIND", "NSE")).cached
    disabled = asyncio.run(company_snapshot(session, Settings(company_research_provider="none"), "AARTIIND", "NSE"))
    assert disabled.status == "unavailable" and disabled.name is None


def test_company_api_auth_search_and_validation(api_context, monkeypatch):
    client, _, _, headers, _ = api_context
    from app.core.config import get_settings
    from app.main import app
    settings = app.dependency_overrides[get_settings]().model_copy(update={"company_research_provider": "yahoo"})
    app.dependency_overrides[get_settings] = lambda: settings
    async def fake(function, *args):
        if function.__name__ == "yahoo_company_search":
            return [{"symbol": "AARTIIND", "exchange": "NSE", "name": "Aarti Industries"}]
        return {"name": "Aarti Industries", "currency": "INR"}
    monkeypatch.setattr("app.services.company_research.provider_call", fake)
    assert client.get("/companies/search?q=Aarti").status_code == 401
    assert client.get("/companies/AARTIIND/snapshot?exchange=NSE").status_code == 401
    response = client.get("/companies/search?q=Aarti", headers=headers)
    assert response.json()["matches"][0]["name"] == "Aarti Industries"
    result = client.get("/companies/AARTIIND/snapshot?exchange=NSE", headers=headers)
    assert result.status_code == 200 and result.json()["status"] == "available"
    assert result.json()["screener_url"] == "https://www.screener.in/company/AARTIIND/consolidated/"
    assert client.get("/companies/AARTIIND/snapshot?exchange=UNKNOWN", headers=headers).status_code == 422
    assert client.get("/companies/search?q=INDS00001", headers=headers).json()["status"] == "unavailable"
