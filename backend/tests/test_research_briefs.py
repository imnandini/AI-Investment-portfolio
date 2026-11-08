import asyncio
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from html import escape
import json
from uuid import UUID, uuid4

import httpx
import pytest

from app.integrations import company_news as news_module
from app.models.holding import Holding
from app.models.indmoney import IndmoneyBalance
from app.models.portfolio import Portfolio
from app.models.user import User
from app.services import research_briefs as briefs

NOW = datetime(2026, 11, 8, 12, tzinfo=timezone.utc)


def feed(*articles):
    items = []
    for article in articles:
        title = article.get("title", "Acme profit rises 20%")
        date = article.get("date", format_datetime(NOW - timedelta(hours=1)))
        link = article.get("url", "https://publisher.example/article")
        items.append(f"<item><title>{escape(title)}</title><link>{escape(link)}</link><pubDate>{escape(date)}</pubDate><source>Example News</source></item>")
    return ("<rss><channel>" + "".join(items) + "</channel></rss>").encode()


def test_news_matching_dates_duplicates_safe_links_and_order():
    articles = news_module.parse_feed(feed(
        {}, {},
        {"title": "Other company profits rise"},
        {"title": "Acme Share Price Live Updates: Latest ticker"},
        {"title": "Acme profit falls", "date": format_datetime(NOW - timedelta(days=31))},
        {"title": "Acme future story", "date": format_datetime(NOW + timedelta(days=1))},
        {"title": "Acme undated story", "date": ""},
        {"title": "Acme unsafe link", "url": "javascript:alert(1)"},
        {"title": "Acme wins a contract", "date": format_datetime(NOW - timedelta(minutes=10))},
    ), "Acme Limited", NOW)
    assert [a["title"] for a in articles] == ["Acme wins a contract", "Acme profit rises 20%"]
    assert [a["id"] for a in articles] == ["news-1", "news-2"]
    assert all(a["publisher"] == "Example News" for a in articles)


@pytest.mark.parametrize("content", [b"<html>Blocked</html>", b"<!DOCTYPE rss><rss/>", b"<!ENTITY x 'bad'><rss/>", b"x" * 1_000_001], ids=["html", "doctype", "entity", "oversized"])
def test_news_rejects_html_dtd_and_oversized_payloads(content):
    with pytest.raises(ValueError):
        news_module.parse_feed(content, "Acme", NOW)


def test_news_fetch_fallback_cache_and_original_check_time(monkeypatch):
    news_module.CACHE.clear()
    monkeypatch.setattr(news_module, "utcnow", lambda: NOW)
    calls = []

    async def fetch(url, params):
        calls.append((url, params))
        if "bing.com" in url:
            raise httpx.ConnectError("private upstream diagnostic")
        return feed({})

    monkeypatch.setattr(news_module, "fetch_feed", fetch)
    first = asyncio.run(news_module.company_news("Acme Ltd"))
    second = asyncio.run(news_module.company_news("Acme Ltd"))
    assert first["status"] == "available" and first["provider"] == "Google News RSS"
    assert not first["cached"] and second["cached"]
    assert first["checked_at"] == second["checked_at"]
    assert len(calls) == 2
    assert all(set(params) <= {"q", "format", "setlang", "mkt", "hl", "gl", "ceid"} for _, params in calls)
    news_module.CACHE.clear()


def test_news_unavailable_and_internal_codes_do_not_produce_fake_articles(monkeypatch):
    news_module.CACHE.clear()

    async def fetch(*args):
        raise httpx.ConnectError("private upstream diagnostic")

    monkeypatch.setattr(news_module, "fetch_feed", fetch)
    result = asyncio.run(news_module.company_news("Acme"))
    assert result["status"] == "unavailable" and result["articles"] == []
    assert "private" not in json.dumps(result)
    result = asyncio.run(news_module.company_news("INDS12345"))
    assert result["status"] == "unavailable" and "company name" in result["note"]
    news_module.CACHE.clear()


@pytest.mark.parametrize("title", [
    "Acme denies fraud probe", "Acme avoids default", "Acme profit expected to rise", "Acme revenue to rise next year", "Acme profit growth slows", "Acme not fined",
])
def test_negation_forecasts_and_ambiguous_headlines_stay_neutral(title):
    articles = [{"title": title, "id": "news-1"}]
    assert briefs.news_signals(articles, briefs.POSITIVE) == []
    assert briefs.news_signals(articles, briefs.NEGATIVE) == []


def stock(api_context, symbol="ACME", quantity="2", average_cost="100"):
    client, user, portfolio, headers, session = api_context
    response = client.post(f"/portfolios/{portfolio.id}/holdings", headers=headers,
        json={"symbol": symbol, "quantity": quantity, "average_cost": average_cost})
    assert response.status_code == 201, response.text
    holding = session.get(Holding, UUID(response.json()["id"]))
    holding.instrument.display_name = "Acme Limited" if symbol == "ACME" else "Other Company"
    session.commit()
    return holding


def news_result():
    return {"status": "available", "checked_at": NOW.isoformat(), "cached": False, "note": "Unverified matched headlines", "provider": "Synthetic news",
        "articles": [{"id": "news-1", "title": "Acme profits rise 20%", "url": "https://publisher.example/growth", "publisher": "Example News", "published_at": NOW.isoformat()},
                     {"id": "news-2", "title": "Acme faces regulatory probe", "url": "https://publisher.example/probe", "publisher": "Example News", "published_at": NOW.isoformat()}]}


def test_stock_brief_has_source_linked_pros_cons_and_no_upload_requirement(api_context, monkeypatch):
    client, user, portfolio, headers, session = api_context
    holding = stock(api_context)
    calls = []

    async def read(name, currency):
        calls.append((name, currency))
        return news_result()

    monkeypatch.setattr(briefs, "company_news", read)
    response = client.post(f"/portfolios/{portfolio.id}/holdings/{holding.id}/brief", headers=headers)
    assert response.status_code == 200, response.text
    brief = response.json()
    assert brief["name"] == "Acme Limited" and "Mixed" in brief["view"]
    assert brief["pros"][0]["source_ids"] == ["news-1"]
    assert brief["cons"][0]["source_ids"] == ["news-2"]
    assert brief["portfolio_context"]["cost_weight_pct"] == "100.00"
    assert brief["portfolio_context"]["market_weight_pct"] is None
    assert "cash" in brief["pros"][0]["explanation"]
    context = next(section["text"] for section in brief["analysis"] if section["title"] == "What this holding means for your portfolio")
    assert "100.00%" in context and "cost basis" in context
    assert "current market weight could differ" in context
    assert brief["evidence"] == []
    assert calls == [("Acme Limited", "INR")]
    assert any("No buy/sell rating" in line for line in brief["limitations"])


def test_brief_owner_and_holding_checks_happen_before_news(api_context, monkeypatch):
    client, user, portfolio, headers, session = api_context
    holding = stock(api_context)
    other = User(email="brief-other@example.com", password_hash="unused")
    session.add(other); session.flush()
    other_portfolio = Portfolio(user_id=other.id, name="Other", base_currency="INR")
    session.add(other_portfolio); session.commit()

    async def forbidden(*args):
        raise AssertionError("Unauthorized request must not query news")

    monkeypatch.setattr(briefs, "company_news", forbidden)
    assert client.post(f"/portfolios/{portfolio.id}/brief").status_code == 401
    assert client.post(f"/portfolios/{other_portfolio.id}/brief", headers=headers).status_code == 404
    assert client.post(f"/portfolios/{other_portfolio.id}/holdings/{holding.id}/brief", headers=headers).status_code == 404
    assert client.post(f"/portfolios/{portfolio.id}/holdings/{uuid4()}/brief", headers=headers).status_code == 404


def test_portfolio_opinion_concentration_uses_cost_when_prices_unknown_and_excludes_pf(api_context, monkeypatch):
    client, user, portfolio, headers, session = api_context
    stock(api_context, quantity="8")
    stock(api_context, symbol="OTHER", quantity="2")
    session.add(IndmoneyBalance(portfolio_id=portfolio.id, asset_key="EPF-1", payload=json.dumps({"symbol": "EPF-1", "display_name": "Provident fund", "market_value": "5000"}), imported_at=NOW))
    session.commit()

    async def read(*args):
        return news_result()

    monkeypatch.setattr(briefs, "company_news", read)
    response = client.post(f"/portfolios/{portfolio.id}/brief", headers=headers)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["weight_basis"] == "cost basis"
    assert "Concentration" in result["view"]
    assert any("80.00%" in item and "Acme Limited" in item for item in result["concerns"])
    assert result["security_count"] == 2 and result["pf_account_count"] == 1
    assert "recorded purchase costs" in result["analysis"][0]["text"]
    assert "PF account balances remain visible separately" in result["analysis"][1]["text"]
    assert len(result["stocks"]) == 2
    assert any("excluded" in item and "PF" in item for item in result["limitations"])


def test_empty_portfolio_and_news_failure_stay_reviewable(api_context, monkeypatch):
    client, user, portfolio, headers, session = api_context
    empty = client.post(f"/portfolios/{portfolio.id}/brief", headers=headers)
    assert empty.status_code == 200 and empty.json()["stocks"] == []
    holding = stock(api_context)

    async def unavailable(*args):
        return {"status": "unavailable", "articles": [], "note": "Feed unavailable", "checked_at": NOW.isoformat(), "cached": False}

    monkeypatch.setattr(briefs, "company_news", unavailable)
    response = client.post(f"/portfolios/{portfolio.id}/holdings/{holding.id}/brief", headers=headers)
    assert response.status_code == 200
    assert response.json()["pros"] == [] and response.json()["cons"] == []
    assert "not enough" in response.json()["view"]
