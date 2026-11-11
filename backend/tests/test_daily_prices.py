from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pandas as pd
import pytest
from sqlalchemy import select

from app.core.config import Settings, get_settings
from app.integrations.daily_prices import ClosingPrices, DailyPriceError, PriceInstrument, resolve_ticker, yahoo_closes
from app.main import app
from app.models.daily_price import DailyPrice, DailyPriceSync
from app.models.indmoney import IndmoneyPrice
from app.models.portfolio import Portfolio
from app.models.user import User
from app.services import daily_prices as service
from app.services.prices import saved_prices


@pytest.fixture
def daily_context(api_context, monkeypatch):
    client, _, portfolio, headers, session = api_context
    app.dependency_overrides[get_settings] = lambda: Settings(secret_key="test-secret-key-with-more-than-32-characters", daily_price_provider="yahoo")
    target = service.through_date()
    calls = []

    def fetch(instrument, through):
        calls.append((instrument, through))
        assert through == target
        return ClosingPrices(instrument.symbol + ".NS", "NSE", "INR", {
            target - timedelta(days=8): Decimal("80"),
            target - timedelta(days=1): Decimal("100"), target: Decimal("110"),
        })

    monkeypatch.setattr(service, "yahoo_closes", fetch)
    result = client.post(f"/portfolios/{portfolio.id}/holdings", headers=headers, json={
        "symbol": "ACME", "exchange": "NSE", "quantity": "2", "average_cost": "90", "sector": "Technology"})
    assert result.status_code == 201
    return api_context, target, calls


def analytics(context):
    client, _, portfolio, headers, _ = context
    result = client.post(f"/portfolios/{portfolio.id}/analytics", headers=headers, json={})
    assert result.status_code == 200, result.text
    return result.json()


def test_auto_closes_value_portfolio_without_manual_entry_and_persist_history(daily_context):
    context, target, calls = daily_context
    result = analytics(context)
    assert result["market_value_total"] == "220.00"
    assert result["unrealized_pl_total"] == "40.00"
    assert result["positions"][0]["price_source"] == "Yahoo Finance"
    assert result["positions"][0]["price_kind"] == "daily_close"
    overview = result["daily_prices"]
    assert overview["requested_through"] == target.isoformat()
    assert overview["latest_date"] == target.isoformat()
    assert overview["comparisons"][0]["change"] == "20.00"
    assert overview["comparisons"][0]["change_pct"] == "10.00"
    assert overview["comparisons"][1]["change"] == "60.00"
    assert "Current quantities" in overview["comparison_basis"]
    analytics(context)
    assert len(calls) == 1
    client, _, portfolio, headers, session = context
    history = client.get(f"/portfolios/{portfolio.id}/prices/history", headers=headers).json()
    assert len(history) == 3
    assert history[-1]["provider_symbol"] == "ACME.NS"
    assert len(list(session.scalars(select(DailyPrice)))) == 3


def test_failed_refresh_keeps_old_price_and_retries_after_backoff(daily_context, monkeypatch):
    context, target, calls = daily_context
    analytics(context)
    session = context[-1]
    state = session.scalar(select(DailyPriceSync))
    state.next_check_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    session.commit()

    def unavailable(*args):
        raise DailyPriceError("Yahoo Finance temporarily limited requests.")

    monkeypatch.setattr(service, "yahoo_closes", unavailable)
    result = analytics(context)
    assert result["market_value_total"] == "220.00"
    assert any("temporarily limited" in note for note in result["daily_prices"]["notes"])
    assert len(list(session.scalars(select(DailyPrice)))) == 3
    state = session.scalar(select(DailyPriceSync).execution_options(populate_existing=True))
    assert service.aware(state.next_check_at) > datetime.now(timezone.utc)


def test_new_automatic_close_replaces_old_manual_price(daily_context):
    context, target, _ = daily_context
    client, _, portfolio, headers, _ = context
    response = client.put(f"/portfolios/{portfolio.id}/prices", headers=headers, json={
        "symbol": "ACME", "exchange": "NSE", "currency": "INR", "price": "50",
        "as_of": (datetime.now(timezone.utc) - timedelta(days=5)).isoformat(), "source": "Yahoo Finance", "kind": "daily_close"})
    assert response.status_code == 200
    assert response.json()["source"] == "Manual reference" and response.json()["kind"] == "reference"
    assert analytics(context)["market_value_total"] == "220.00"


def test_newer_imported_price_is_not_masked_by_old_reference(daily_context):
    import json
    context, _, _ = daily_context
    client, _, portfolio, headers, session = context
    client.put(f"/portfolios/{portfolio.id}/prices", headers=headers, json={
        "symbol": "ACME", "exchange": "NSE", "currency": "INR", "price": "50",
        "as_of": (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()})
    session.add(IndmoneyPrice(portfolio_id=portfolio.id, symbol="ACME", exchange="NSE", payload=json.dumps({
        "symbol": "ACME", "exchange": "NSE", "currency": "INR", "price": "120", "as_of": datetime.now(timezone.utc).isoformat()})))
    session.commit()
    result = analytics(context)
    assert result["market_value_total"] == "240.00"
    assert result["positions"][0]["price_source"] == "INDmoney"


def test_partial_or_mixed_currency_history_never_invents_portfolio_comparison(daily_context):
    context, _, _ = daily_context
    client, _, portfolio, headers, _ = context
    client.post(f"/portfolios/{portfolio.id}/holdings", headers=headers, json={
        "symbol": "OTHER", "exchange": "NYSE", "currency": "USD", "quantity": "1", "average_cost": "10"})
    result = analytics(context)
    assert not result["daily_prices"]["comparisons"]
    assert result["market_value_total"] is None


def test_owner_check_precedes_provider_io(daily_context):
    context, _, calls = daily_context
    client, _, _, headers, _ = context
    assert client.post(f"/portfolios/{uuid4()}/analytics", headers=headers, json={}).status_code == 404
    assert client.get(f"/portfolios/{uuid4()}/prices/history", headers=headers).status_code == 404
    assert not calls


def test_history_cannot_read_another_owners_saved_prices(daily_context):
    context, _, calls = daily_context
    client, _, _, headers, session = context
    other = User(email="daily-other@example.com", password_hash="unused")
    session.add(other)
    session.flush()
    foreign = Portfolio(user_id=other.id, name="Foreign", base_currency="INR")
    session.add(foreign)
    session.commit()
    assert client.get(f"/portfolios/{foreign.id}/prices/history", headers=headers).status_code == 404
    assert client.post(f"/portfolios/{foreign.id}/analytics", headers=headers, json={}).status_code == 404
    assert not calls


def test_current_day_bars_are_not_saved(daily_context, monkeypatch):
    context, target, _ = daily_context
    monkeypatch.setattr(service, "yahoo_closes", lambda instrument, through: ClosingPrices("ACME.NS", "NSE", "INR", {
        target: Decimal("110"), target + timedelta(days=1): Decimal("9999")}))
    result = analytics(context)
    assert result["market_value_total"] == "220.00"
    assert len(list(context[-1].scalars(select(DailyPrice)))) == 1


def test_delayed_weekday_close_is_rechecked_before_next_day(daily_context, monkeypatch):
    context, target, _ = daily_context
    if target.weekday() >= 5:
        pytest.skip("A weekend close is expected to fall on an earlier trading day.")
    monkeypatch.setattr(service, "yahoo_closes", lambda instrument, through: ClosingPrices("ACME.NS", "NSE", "INR", {
        target - timedelta(days=1): Decimal("110")}))
    result = analytics(context)
    assert result["daily_prices"]["latest_date"] == (target - timedelta(days=1)).isoformat()
    state = context[-1].scalar(select(DailyPriceSync))
    assert service.aware(state.next_check_at) <= datetime.now(timezone.utc) + timedelta(hours=2)


def test_ticker_resolution_never_uses_internal_indmoney_code_or_fuzzy_name():
    queries = []
    def search(name):
        queries.append(name)
        return [{"symbol": "ACME.NS", "quoteType": "EQUITY", "longname": "Acme Ltd"},
                {"symbol": "ACME.BO", "quoteType": "EQUITY", "longname": "Acme Limited"},
                {"symbol": "BAD.NS", "quoteType": "EQUITY", "longname": "Acme Finance Limited"}]
    instrument = PriceInstrument("INDS12345", "UNKNOWN", "INR", "EQUITY", "Acme Limited")
    assert resolve_ticker(instrument, search) == "ACME.NS"
    assert queries == ["Acme Limited"]
    with pytest.raises(DailyPriceError):
        resolve_ticker(PriceInstrument("INDS12345", "UNKNOWN", "INR", "EQUITY"), search)
    with pytest.raises(DailyPriceError):
        resolve_ticker(PriceInstrument("INDS12345", "UNKNOWN", "INR", "EQUITY", "Acme"),
                       lambda name: [{"symbol": "BAD.NS", "quoteType": "EQUITY", "longname": "Acme Finance"}])


def test_yahoo_adapter_validates_currency_and_preserves_close_dates(monkeypatch):
    import yfinance as yf
    target = service.through_date()
    arguments = []
    class Ticker:
        def history(self, **kwargs):
            arguments.append(kwargs)
            return pd.DataFrame({"Close": [100.0, 110.0, float("nan")]},
                                index=pd.to_datetime([target - timedelta(days=1), target, target + timedelta(days=1)]))
        def get_history_metadata(self):
            return {"currency": "INR", "exchangeName": "NSI", "instrumentType": "EQUITY"}
    monkeypatch.setattr(yf, "Ticker", lambda symbol: Ticker())
    result = yahoo_closes(PriceInstrument("ACME", "NSE", "INR", "EQUITY"), target)
    assert result.closes[target] == Decimal("110")
    assert max(result.closes) == target
    assert arguments[0]["auto_adjust"] is False
    assert arguments[0]["end"] == (target + timedelta(days=1)).isoformat()
    with pytest.raises(DailyPriceError, match="currency"):
        yahoo_closes(PriceInstrument("ACME", "NSE", "USD", "EQUITY"), target)
    monkeypatch.setattr(Ticker, "get_history_metadata", lambda self: {"currency": "USD", "exchangeName": "NYQ", "instrumentType": "EQUITY"})
    with pytest.raises(DailyPriceError, match="exchange"):
        yahoo_closes(PriceInstrument("ACME", "NASDAQ", "USD", "EQUITY"), target)


def test_no_provider_preserves_existing_manual_workflow(api_context):
    result = analytics(api_context)
    assert not result["daily_prices"]["configured"]
