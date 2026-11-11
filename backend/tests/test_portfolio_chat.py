from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from app.models.holding import Holding
from app.services import research_briefs


@pytest.fixture
def news_calls(monkeypatch):
    calls = []

    async def news(name, currency):
        calls.append((name, currency))
        return {"status": "available", "checked_at": "2026-11-11T09:00:00+00:00", "cached": False,
                "provider": "Test feed", "note": "Matched headlines; full articles are not verified.",
                "articles": [{"id": "news-1", "title": f"{name} profits rise 20%", "publisher": "Test News",
                              "url": "https://example.org/results", "published_at": "2026-11-10T09:00:00+00:00"}]}

    monkeypatch.setattr(research_briefs, "company_news", news)
    return calls


def add_holding(context, symbol="ACME", name="Acme Limited", quantity="8", cost="100", **fields):
    client, _, portfolio, headers, session = context
    created = client.post(f"/portfolios/{portfolio.id}/holdings", headers=headers,
                          json={"symbol": symbol, "quantity": quantity, "average_cost": cost, **fields})
    assert created.status_code == 201, created.text
    holding = session.get(Holding, UUID(created.json()["id"]))
    holding.instrument.display_name = name
    session.commit()
    return holding


def ask(context, question):
    client, _, portfolio, headers, _ = context
    result = client.post(f"/portfolios/{portfolio.id}/chat", headers=headers, json={"question": question})
    assert result.status_code == 200, result.text
    return result.json()["response"]


def test_overall_question_without_documents_uses_real_portfolio_and_keeps_history(api_context, news_calls):
    add_holding(api_context)
    add_holding(api_context, "OTHER", "Other Company", "2")
    response = ask(api_context, "Is my overall portfolio okay?")
    assert response["status"] == "supported"
    assert response["method"] == "portfolio-chat-v1"
    assert response["evidence"] == []
    assert "80.00%" in response["answer"] and "cost basis" in response["answer"]
    assert "Only 0 of 2" in response["answer"]
    assert "goals" in response["answer"]
    assert len(response["news"]) == 2
    assert news_calls == [("Acme Limited", "INR"), ("Other Company", "INR")]
    client, _, portfolio, headers, _ = api_context
    history = client.get(f"/portfolios/{portfolio.id}/chat", headers=headers).json()
    assert history[0]["response"] == response
    assert client.delete(f"/portfolios/{portfolio.id}/chat", headers=headers).status_code == 204
    assert client.get(f"/portfolios/{portfolio.id}/chat", headers=headers).json() == []


@pytest.mark.parametrize("question", ["What is Acme doing currently?", "What's the latest news on ACME?", "Is Acme okay?"])
def test_named_company_uses_only_its_public_name(api_context, news_calls, question):
    add_holding(api_context)
    add_holding(api_context, "OTHER", "Other Company", "2")
    response = ask(api_context, question)
    assert news_calls == [("Acme Limited", "INR")]
    assert "Acme Limited profits rise" in response["answer"]
    assert response["news"][0]["articles"][0]["url"] == "https://example.org/results"
    assert response["news"][0]["checked_at"]


def test_general_company_updates_without_documents(api_context, news_calls):
    add_holding(api_context)
    response = ask(api_context, "What are my companies doing currently?")
    assert "Acme Limited profits rise" in response["answer"]
    assert response["news"] and not response["evidence"]


def test_saved_performance_math_does_not_require_news(api_context, news_calls):
    add_holding(api_context, quantity="2")
    client, _, portfolio, headers, _ = api_context
    assert client.put(f"/portfolios/{portfolio.id}/prices", headers=headers, json={
        "symbol": "ACME", "price": "120", "currency": "INR", "as_of": datetime.now(timezone.utc).isoformat(),
    }).status_code == 200
    response = ask(api_context, "How much is my portfolio worth and what is my profit?")
    assert "200.00 INR" in response["answer"]
    assert "240.00 INR" in response["answer"]
    assert "40.00 INR" in response["answer"]
    assert "not a live quote" in response["answer"]
    assert not news_calls


def test_missing_costs_are_not_zero_filled(api_context, news_calls):
    holding = add_holding(api_context)
    api_context[-1].get(Holding, holding.id).average_cost = None
    api_context[-1].commit()
    response = ask(api_context, "What is my portfolio value?")
    assert "Recorded cost basis: unavailable" in response["answer"]
    assert "Market value: unavailable" in response["answer"]
    assert "cost basis unknown" in response["answer"]


def test_news_failure_still_answers_overall_question(api_context, monkeypatch):
    add_holding(api_context)

    async def unavailable(*args):
        return {"status": "unavailable", "articles": [], "note": "News feeds are temporarily unavailable.",
                "checked_at": "2026-11-11T09:00:00+00:00", "cached": False}

    monkeypatch.setattr(research_briefs, "company_news", unavailable)
    response = ask(api_context, "Is my portfolio okay?")
    assert "100.00%" in response["answer"]
    assert response["news"][0]["status"] == "unavailable"
    response = ask(api_context, "What is Acme doing currently?")
    assert "cannot confirm" in response["answer"]
    assert "temporarily unavailable" in response["answer"]


def test_empty_portfolio_and_unknown_company_do_not_invent_context(api_context, news_calls):
    response = ask(api_context, "Is my portfolio okay?")
    assert "No security holdings" in response["answer"]
    add_holding(api_context)
    response = ask(api_context, "What is Unknown Corp doing currently?")
    assert response["status"] == "insufficient_evidence"
    assert "could not match" in response["answer"]
    assert not news_calls


def test_foreign_portfolio_checks_happen_before_any_news(api_context, news_calls):
    client, _, _, headers, _ = api_context
    assert client.post(f"/portfolios/{uuid4()}/chat", headers=headers, json={"question": "latest news"}).status_code == 404
    assert not news_calls


def test_definition_is_available_without_documents_or_news(api_context, news_calls):
    response = ask(api_context, "What is diversification?")
    assert "spreads exposure" in response["answer"]
    assert response["status"] == "supported" and not news_calls


def test_optional_document_search_failure_does_not_block_portfolio_answer(api_context, news_calls, monkeypatch):
    add_holding(api_context)

    def unavailable(*args):
        raise RuntimeError("private diagnostic")

    monkeypatch.setattr("app.api.chat.retrieve", unavailable)
    response = ask(api_context, "Is my portfolio okay?")
    assert "100.00%" in response["answer"]
    assert any("could not be searched" in item for item in response["limitations"])
    assert "private diagnostic" not in str(response)
