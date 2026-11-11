from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select
from pydantic import ValidationError

from app.agents.portfolio_review import nodes
from app.agents.portfolio_review.report import ReviewReport
from app.models.data_source import ManualPrice
from app.models.holding import Holding
from app.models.instrument import Instrument
from app.models.portfolio import Portfolio
from app.models.user import User


def seed(context, count=2, fund=False):
    _, _, portfolio, _, session = context
    for index in range(count):
        name = "Acme Limited" if index == 0 else "Index ETF" if fund and index == 1 else f"Company {index} Limited"
        instrument = Instrument(canonical_symbol=f"INDS{index:05}", display_name=name, exchange="NSE", asset_type="EQUITY", currency="INR", sector="Technology")
        session.add(instrument)
        session.flush()
        cost = Decimal(count - index) * Decimal(100)
        session.add(Holding(portfolio_id=portfolio.id, instrument_id=instrument.id, quantity=Decimal(1), average_cost=cost))
        session.add(ManualPrice(portfolio_id=portfolio.id, symbol=instrument.canonical_symbol, exchange="NSE", payload={
            "symbol": instrument.canonical_symbol, "exchange": "NSE", "currency": "INR", "price": str(cost * Decimal("1.1")), "as_of": datetime.now(timezone.utc).isoformat()}))
    session.commit()


def feed(name):
    now = datetime.now(timezone.utc)
    return {"status": "available", "checked_at": now.isoformat(), "cached": False, "provider": "Test news",
            "note": "Matched recent headlines; full articles are not verified.", "articles": [
                {"id": "news-1", "title": f"{name} profits rise 20%", "url": f"https://example.org/{name.replace(' ', '-')}/results", "publisher": "Test publisher", "published_at": (now - timedelta(days=1)).isoformat()},
                {"id": "news-2", "title": f"{name} faces regulatory probe", "url": f"https://example.org/{name.replace(' ', '-')}/probe", "publisher": "Test publisher", "published_at": (now - timedelta(days=2)).isoformat()},
            ]}


def launch(context):
    client, _, portfolio, headers, _ = context
    response = client.post(f"/portfolios/{portfolio.id}/reviews", headers=headers)
    assert response.status_code == 201, response.text
    assert response.json()["status"] != "failed", response.text
    return response.json()


def test_review_without_documents_has_named_specific_assessment_news_and_valid_sources(api_context, monkeypatch):
    seed(api_context)
    calls = []
    async def news(name, currency):
        calls.append((name, currency))
        return feed(name)
    monkeypatch.setattr(nodes, "company_news", news)
    result = launch(api_context)
    report = result["report"]
    assert report["methodology_version"] == "portfolio-review-v2"
    assert report["evidence"] == []
    assert "Acme Limited" in report["summary"] and "66.67%" in report["summary"]
    assert any("6.67%" in finding["text"] and "10%" in finding["text"] for finding in report["findings"])
    assert "INDS00000" not in report["summary"]
    assert report["coverage"]["checked_positions"] == 2
    assert report["coverage"]["positions_with_news"] == 2
    assert report["coverage"]["checked_weight_pct"] == "100.00"
    assert not any("no matching document" in item.lower() for item in report["limitations"])
    assert result["status"] == "complete", "Optional documents and general caveats must not force partial coverage."
    sources = {article["id"] for company in report["company_reviews"] for article in company["news"]["articles"]}
    assert len(sources) == 4
    signals = [finding for finding in report["findings"] if finding["basis"] == "headline_signal"]
    assert signals and all(set(finding["source_ids"]) <= sources for finding in signals)
    assert calls == [("Acme Limited", "INR"), ("Company 1 Limited", "INR")]
    client, _, portfolio, headers, _ = api_context
    assert client.get(f"/portfolios/{portfolio.id}/reviews/{result['id']}", headers=headers).json()["report"] == report


def test_hundred_holdings_are_calculated_with_bounded_transparent_news_sample(api_context, monkeypatch):
    seed(api_context, count=100)
    calls = []
    async def news(name, currency):
        calls.append(name)
        return feed(name)
    monkeypatch.setattr(nodes, "company_news", news)
    result = launch(api_context)
    report = result["report"]
    assert len(report["analytics"]["positions"]) == 100
    assert len(calls) == 20
    assert report["coverage"]["eligible_positions"] == 100
    assert report["coverage"]["unreviewed_positions"] == 80
    assert "Company 19 Limited" in calls and "Company 20 Limited" not in calls
    assert result["status"] == "partial"
    assert "sector exposure" in report["summary"]
    assert any("80" in item and "not checked" in item for item in report["limitations"])


def test_fund_is_not_treated_as_operating_company_earnings(api_context, monkeypatch):
    seed(api_context, fund=True)
    async def news(name, currency):
        return feed(name)
    monkeypatch.setattr(nodes, "company_news", news)
    report = launch(api_context)["report"]
    fund = next(company for company in report["company_reviews"] if company["name"] == "Index ETF")
    assert fund["is_fund"] and "underlying" in fund["view"]
    assert fund["positive_signals"] == [] and fund["concern_signals"] == []
    assert any("Index ETF" in question for question in report["follow_up_questions"])


def test_news_failure_preserves_calculations_and_does_not_request_uploads(api_context, monkeypatch):
    seed(api_context)
    async def broken(*args):
        raise RuntimeError("private upstream diagnostic")
    monkeypatch.setattr(nodes, "company_news", broken)
    result = launch(api_context)
    report = result["report"]
    assert result["status"] == "partial"
    assert report["analytics"]["market_value_total"] == "330.00"
    assert report["coverage"]["positions_without_news"] == 2
    assert "Acme Limited" in report["summary"]
    assert "private upstream" not in str(report)
    assert not any("upload" in note.lower() for note in report["limitations"])


def test_access_denial_happens_before_any_public_news_request(api_context, monkeypatch):
    client, _, _, headers, session = api_context
    other = User(email="foreign-review@example.com", password_hash="unused")
    session.add(other); session.flush()
    portfolio = Portfolio(user_id=other.id, name="Foreign", base_currency="INR")
    session.add(portfolio); session.commit()
    async def forbidden(*args):
        raise AssertionError("Foreign portfolio must not query public news")
    monkeypatch.setattr(nodes, "company_news", forbidden)
    assert client.post(f"/portfolios/{portfolio.id}/reviews", headers=headers).status_code == 404


def test_news_findings_cannot_reference_missing_sources():
    with pytest.raises(ValidationError, match="news sources"):
        ReviewReport(summary="test", analytics={}, findings=[{"title": "Claim", "text": "Unsupported", "basis": "headline_signal", "source_ids": ["missing"]}],
                     evidence=[], limitations=[], follow_up_questions=[], activities=[])
