from app.models.portfolio import Portfolio


def test_analytics_api_returns_methodology_and_missing_price_state(api_context):
    client, user, portfolio, headers, session = api_context
    response = client.post(
        f"/portfolios/{portfolio.id}/holdings",
        headers=headers,
        json={"symbol": "INFY", "exchange": "NSE", "sector": "Technology", "quantity": "2", "average_cost": "100"},
    )
    assert response.status_code == 201

    response = client.post(f"/portfolios/{portfolio.id}/analytics", headers=headers, json={})
    assert response.status_code == 200
    data = response.json()
    assert data["cost_basis_total"] == "200.00"
    assert data["market_value_total"] is None
    assert data["complete"] is False
    assert data["positions"][0]["price_status"] == "missing"
    assert "saved price" in data["methodology"]


def test_analytics_exposes_holding_and_weighted_portfolio_returns(api_context):
    from datetime import datetime, timezone
    client, _, portfolio, headers, _ = api_context
    for symbol, quantity, cost in [("AAA", "2", "100"), ("BBB", "1", "200")]:
        response = client.post(f"/portfolios/{portfolio.id}/holdings", headers=headers,
                               json={"symbol": symbol, "exchange": "NSE", "quantity": quantity, "average_cost": cost})
        assert response.status_code == 201
    response = client.post(f"/portfolios/{portfolio.id}/analytics", headers=headers, json={"prices": [
        {"symbol": symbol, "exchange": "NSE", "price": price, "currency": "INR", "as_of": datetime.now(timezone.utc).isoformat()}
        for symbol, price in [("AAA", "125"), ("BBB", "180")]]})
    assert response.status_code == 200, response.text
    result = response.json()
    assert [item["unrealized_return_pct"] for item in result["positions"]] == ["25.00", "-10.00"]
    assert result["unrealized_return_pct"] == "7.50"


def test_analytics_api_requires_auth_and_hides_other_users_portfolios(api_context):
    client, user, portfolio, headers, session = api_context
    response = client.post(f"/portfolios/{portfolio.id}/analytics", json={})
    assert response.status_code == 401

    other = Portfolio(user_id=None, name="Other", base_currency="INR")
    from app.models.user import User
    other_user = User(email="other@example.com", password_hash="unused")
    session.add(other_user)
    session.flush()
    other.user_id = other_user.id
    session.add(other)
    session.commit()

    response = client.post(f"/portfolios/{other.id}/analytics", headers=headers, json={})
    assert response.status_code == 404


def test_csv_import_reports_invalid_rows_and_imports_valid_rows(api_context):
    client, user, portfolio, headers, session = api_context
    csv_content = (
        "symbol,exchange,asset_type,currency,sector,quantity,average_cost,purchase_date\n"
        "INFY,NSE,EQUITY,INR,Technology,2,100,2024-01-01\n"
        "BAD,NSE,EQUITY,INR,Technology,-1,5,2024-01-01\n"
    )
    response = client.post(
        f"/portfolios/{portfolio.id}/holdings/import",
        headers=headers,
        files={"file": ("holdings.csv", csv_content, "text/csv")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["imported_count"] == 1
    assert data["errors"][0]["row"] == 3
    assert data["holdings"][0]["instrument"]["sector"] == "Technology"
