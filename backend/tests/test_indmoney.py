import asyncio
import base64
from contextlib import asynccontextmanager
from datetime import timedelta
import hashlib
import json
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

from cryptography.fernet import Fernet
import httpx
import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.integrations import indmoney as provider
from app.main import app
from app.models.indmoney import IndmoneyConnection, IndmoneyPreview
from app.models.portfolio import Portfolio
from app.models.user import User
from app.services.indmoney import normalize


@pytest.fixture
def indmoney(api_context, monkeypatch):
    client, user, portfolio, headers, session = api_context
    settings = app.dependency_overrides[get_settings]()
    settings.indmoney_token_key = Fernet.generate_key().decode()
    app.dependency_overrides[get_settings] = lambda: settings
    requests = []

    def handle(request):
        requests.append(request)
        path = request.url.path
        if "oauth-protected-resource" in path:
            body = {"resource": provider.RESOURCE, "authorization_servers": [provider.ORIGIN + "/"]}
        elif "oauth-authorization-server" in path:
            body = {"issuer": provider.ORIGIN + "/", "authorization_endpoint": provider.ORIGIN + "/authorize",
                "token_endpoint": provider.ORIGIN + "/token", "registration_endpoint": provider.ORIGIN + "/register",
                "code_challenge_methods_supported": ["S256"], "token_endpoint_auth_methods_supported": ["client_secret_post"]}
        elif path == "/register":
            body = {"client_id": "registered-client", "client_secret": "registration-secret", "token_endpoint_auth_method": "client_secret_post"}
        elif path == "/token":
            body = {"access_token": "private-access-token", "refresh_token": "private-refresh-token", "token_type": "Bearer", "expires_in": 3600, "scope": "portfolio:read"}
        else:
            raise AssertionError(path)
        return httpx.Response(200, json=body)

    monkeypatch.setattr(provider, "http_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handle)))
    return (*api_context, settings, requests)


def authorize(context):
    client, user, portfolio, headers, session, settings, requests = context
    start = client.post("/integrations/indmoney/connect", headers=headers)
    assert start.status_code == 200, start.text
    state = start.json()["state"]
    finished = client.post("/integrations/indmoney/callback", headers=headers, json={"code": "one-use-code", "state": state})
    assert finished.status_code == 200, finished.text
    return state


def test_oauth_pkce_scope_encryption_and_replay(indmoney):
    client, user, portfolio, headers, session, settings, requests = indmoney
    start = client.post("/integrations/indmoney/connect", headers=headers).json()
    query = parse_qs(urlsplit(start["authorization_url"]).query)
    assert query["scope"] == ["portfolio:read"]
    assert query["resource"] == [provider.RESOURCE]
    assert query["code_challenge_method"] == ["S256"]
    connection = session.get(IndmoneyConnection, user.id)
    pending = provider.unseal(settings, connection.pending)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(pending["verifier"].encode()).digest()).decode().rstrip("=")
    assert query["code_challenge"] == [challenge]
    assert start["state"] not in connection.pending
    wrong = client.post("/integrations/indmoney/callback", headers=headers, json={"code": "one-use-code", "state": "x" * 43})
    assert wrong.status_code == 400
    callback = {"code": "one-use-code", "state": start["state"]}
    assert client.post("/integrations/indmoney/callback", headers=headers, json=callback).status_code == 200
    session.refresh(connection)
    assert "private-access-token" not in connection.credentials
    assert "registration-secret" not in connection.credentials
    assert connection.pending is None
    assert client.post("/integrations/indmoney/callback", headers=headers, json=callback).status_code == 400
    status = client.get("/integrations/indmoney", headers=headers)
    assert status.json()["connected"]
    assert "private-" not in status.text
    form = parse_qs(next(req.content.decode() for req in requests if req.url.path == "/token"))
    assert form["code_verifier"] == [pending["verifier"]]
    assert form["client_secret"] == ["registration-secret"]


def test_expired_and_other_user_states_are_rejected(indmoney):
    client, user, portfolio, headers, session, settings, requests = indmoney
    start = client.post("/integrations/indmoney/connect", headers=headers).json()
    connection = session.get(IndmoneyConnection, user.id)
    connection.state_expires_at = provider.now() - timedelta(seconds=1)
    session.commit()
    result = client.post("/integrations/indmoney/callback", headers=headers, json={"code": "code", "state": start["state"]})
    assert result.status_code == 400
    assert not any(req.url.path == "/token" for req in requests)
    assert client.post("/integrations/indmoney/connect").status_code == 401


def test_token_refresh_keeps_rotated_tokens_encrypted(indmoney):
    client, user, portfolio, headers, session, settings, requests = indmoney
    authorize(indmoney)
    connection = session.get(IndmoneyConnection, user.id)
    credentials = provider.unseal(settings, connection.credentials)
    credentials["token"]["expires_at"] = (provider.now() - timedelta(seconds=5)).isoformat()
    connection.credentials = provider.seal(settings, credentials)
    session.commit()
    assert asyncio.run(provider.access_token(session, user.id, settings)) == "private-access-token"
    last_request = requests[-1]
    assert parse_qs(last_request.content.decode())["grant_type"] == ["refresh_token"]
    assert "private-refresh-token" not in connection.credentials


def test_unsupported_oauth_host_and_bad_key_fail_closed(indmoney):
    *_, settings, requests = indmoney
    with pytest.raises(provider.IndmoneyError):
        provider.trusted_url("https://attacker.example/token")
    settings.indmoney_token_key = ""
    with pytest.raises(provider.IndmoneyError):
        provider.seal(settings, {"access_token": "secret"})


def test_normalization_aggregates_brokers_and_keeps_unknown_cost():
    rows, warnings = normalize({"data": {"holdings": [
        {"symbol": "INFY", "exchange": "NSE", "units": "2", "invested_amount": "200"},
        {"symbol": "INFY", "exchange": "NSE", "units": "3", "invested_amount": "450"},
        {"symbol": "TCS", "exchange": "NSE", "units": "1", "invested_amount": "unknown", "unit_price": "100"},
        {"name": "Unidentified asset", "units": "4"},
    ]}}, "IND_STOCK")
    assert len(rows) == 2
    assert rows[0]["quantity"] == "5.0000000000"
    assert rows[0]["average_cost"] == "130.0000000000"
    assert rows[1]["average_cost"] is None
    assert rows[1]["price"]["as_of"] is None
    assert len(warnings) == 2


def test_normalization_accepts_indmoney_investment_codes_in_json_result():
    # Matches the private MCP envelope and field names; values are synthetic.
    payload = {"result": json.dumps({"positions": None, "holdings": [
        {"investment_code": "INDS00001", "investment": "Synthetic stock A",
         "asset_type": "STOCK", "total_units": 2, "invested_amount": 200.0,
         "unit_price": 125.0, "market_value": 250.0},
        {"investment_code": "INDS00002", "investment": "Synthetic stock B",
         "asset_type": "STOCK", "total_units": 3, "invested_amount": 450.0,
         "unit_price": 160.0, "market_value": 480.0},
    ], "asset_summary": {"total_value": 730.0}})}
    rows, warnings = normalize(payload, "IND_STOCK")
    assert warnings == []
    assert [row["symbol"] for row in rows] == ["INDS00001", "INDS00002"]
    assert [row["quantity"] for row in rows] == ["2.0000000000", "3.0000000000"]
    assert [row["average_cost"] for row in rows] == ["100.0000000000", "150.0000000000"]
    assert all(row["currency"] == "INR" and row["asset_type"] == "EQUITY" for row in rows)
    assert all(row["exchange"] == "UNKNOWN" and row["price"]["as_of"] is None for row in rows)


@pytest.mark.parametrize("asset_type,currency", [("IND_STOCK", "INR"), ("US_STOCK", "USD")])
def test_stock_asset_label_uses_requested_market_for_currency(asset_type, currency):
    rows, warnings = normalize({"holdings": [{"investment_code": "TEST", "asset_type": "STOCK", "total_units": 1}]}, asset_type)
    assert len(rows) == 1
    assert rows[0]["asset_type"] == "EQUITY"
    assert rows[0]["currency"] == currency
    assert rows[0]["average_cost"] is None
    assert len(warnings) == 1 and "purchase cost is unknown" in warnings[0]


def test_normalization_reports_specific_skipped_row_reasons():
    rows, warnings = normalize({"holdings": [
        {"investment": "Name without an identifier", "total_units": 2},
        {"investment_code": "TEST", "total_units": None},
        {"investment_code": "TEST", "total_units": 2, "currency": "invalid"},
    ]}, "IND_STOCK")
    assert rows == []
    assert "missing symbol, ISIN, scheme code or investment code" in warnings[0]
    assert "missing or non-positive quantity" in warnings[1]
    assert warnings[2] == "Row 3: skipped because these fields are invalid: currency."


@pytest.mark.parametrize("payload", [
    {"holdings": [], "has_more": True}, {"data": {"holdings": [], "next_cursor": "cursor"}},
    {"holdings": [], "total_count": 5}, {"success": False, "holdings": []}, {"message": "No structured holdings"},
])
def test_incomplete_or_unknown_payload_never_imports(payload):
    with pytest.raises(provider.IndmoneyError):
        normalize(payload, "IND_STOCK")


def test_preview_import_idempotency_unknown_cost_analytics_and_manual_conflicts(indmoney, monkeypatch):
    client, user, portfolio, headers, session, settings, requests = indmoney
    authorize(indmoney)
    manual = client.post(f"/portfolios/{portfolio.id}/holdings", headers=headers,
        json={"symbol": "MANUAL", "exchange": "NSE", "quantity": "1", "average_cost": "10"})
    assert manual.status_code == 201
    snapshot = {"holdings": [
        {"symbol": "INFY", "exchange": "NSE", "quantity": "2", "invested_amount": "200", "unit_price": "120", "as_of": provider.now().isoformat()},
        {"symbol": "TCS", "exchange": "NSE", "quantity": "3", "unit_price": "50", "as_of": provider.now().isoformat()},
        {"symbol": "MANUAL", "exchange": "NSE", "quantity": "999", "invested_amount": "999"},
    ]}
    async def read(token, asset_type=None):
        assert token == "private-access-token"
        return snapshot
    monkeypatch.setattr(provider, "read_holdings", read)
    path = f"/integrations/indmoney/portfolios/{portfolio.id}"
    preview = client.post(path + "/preview", headers=headers, json={"asset_type": "IND_STOCK"})
    assert preview.status_code == 200, preview.text
    assert len(client.get(f"/portfolios/{portfolio.id}/holdings", headers=headers).json()) == 1
    assert preview.json()["rows"][2]["conflict"]
    body = {"preview_id": preview.json()["preview_id"]}
    result = client.post(path + "/sync", headers=headers, json=body)
    assert result.status_code == 200, result.text
    assert (result.json()["added"], result.json()["skipped"]) == (2, 1)
    assert client.post(path + "/sync", headers=headers, json=body).status_code == 409
    holdings = client.get(f"/portfolios/{portfolio.id}/holdings", headers=headers).json()
    assert len(holdings) == 3
    assert next(h for h in holdings if h["instrument"]["canonical_symbol"] == "MANUAL")["quantity"] == "1.0000000000"
    analytics = client.post(f"/portfolios/{portfolio.id}/analytics", headers=headers, json={})
    assert analytics.status_code == 200, analytics.text
    assert analytics.json()["cost_basis_total"] is None
    unknown = next(p for p in analytics.json()["positions"] if p["symbol"] == "TCS")
    assert unknown["cost_basis"] is None and unknown["unrealized_pl"] is None
    assert unknown["market_value"] == "150.00"
    assert unknown["price_status"] == "available"
    snapshot["holdings"][0]["quantity"] = "4"
    next_preview = client.post(path + "/preview", headers=headers, json={"asset_type": "IND_STOCK"}).json()
    repeated = client.post(path + "/sync", headers=headers, json={"preview_id": next_preview["preview_id"]})
    assert repeated.json()["added"] == 0 and repeated.json()["updated"] == 2
    assert len(client.get(f"/portfolios/{portfolio.id}/holdings", headers=headers).json()) == 3


def test_provider_investment_codes_survive_preview_sync_and_analytics(indmoney, monkeypatch):
    client, user, portfolio, headers, session, settings, requests = indmoney
    authorize(indmoney)

    async def read(*args):
        return {"result": json.dumps({"holdings": [
            {"investment_code": "INDS00001", "investment": "Synthetic stock",
             "asset_type": "STOCK", "total_units": 2, "invested_amount": 200.0,
             "unit_price": 125.0},
        ]})}

    monkeypatch.setattr(provider, "read_holdings", read)
    path = f"/integrations/indmoney/portfolios/{portfolio.id}"
    preview = client.post(path + "/preview", headers=headers, json={"asset_type": "IND_STOCK"})
    assert preview.status_code == 200, preview.text
    assert preview.json()["warnings"] == []
    assert preview.json()["rows"][0]["symbol"] == "INDS00001"
    result = client.post(path + "/sync", headers=headers, json={"preview_id": preview.json()["preview_id"]})
    assert result.status_code == 200, result.text
    assert result.json()["added"] == 1
    holdings = client.get(f"/portfolios/{portfolio.id}/holdings", headers=headers).json()
    assert len(holdings) == 1 and holdings[0]["source"] == "indmoney"
    assert holdings[0]["instrument"]["display_name"] == "Synthetic stock"
    analytics = client.post(f"/portfolios/{portfolio.id}/analytics", headers=headers, json={})
    assert analytics.status_code == 200, analytics.text
    assert analytics.json()["cost_basis_total"] == "200.00"
    assert analytics.json()["positions"][0]["price_status"] == "unknown_freshness"

    # Refreshes enrich an existing imported instrument without changing identity.
    from app.models.instrument import Instrument
    instrument = session.scalar(select(Instrument).where(Instrument.canonical_symbol == "INDS00001"))
    instrument.display_name = None
    session.commit()
    repeated = client.post(path + "/preview", headers=headers, json={"asset_type": "IND_STOCK"}).json()
    refreshed = client.post(path + "/sync", headers=headers, json={"preview_id": repeated["preview_id"]})
    assert refreshed.json()["updated"] == 1 and refreshed.json()["added"] == 0
    assert client.get(f"/portfolios/{portfolio.id}/holdings", headers=headers).json()[0]["instrument"]["display_name"] == "Synthetic stock"


@pytest.mark.parametrize("asset_type", ["EPF", "PPF"])
def test_pf_balance_normalization_requires_no_invented_security_units(asset_type):
    rows, warnings = normalize({"holdings": [{"investment": "Provident fund", "investment_code": None,
        "asset_type": asset_type, "total_units": None, "unit_price": None,
        "invested_amount": 5000, "market_value": 5500}]}, asset_type)
    assert warnings == []
    assert len(rows) == 1 and rows[0]["kind"] == "balance"
    assert rows[0]["currency"] == "INR"
    assert rows[0]["market_value"] == "5500.0000000000"
    assert rows[0]["as_of"] is None
    assert "quantity" not in rows[0] and "average_cost" not in rows[0]


@pytest.mark.parametrize("balance", [None, "not available", -1])
def test_pf_missing_or_invalid_balances_are_not_inferred(balance):
    rows, warnings = normalize({"holdings": [{"investment": "Provident fund", "market_value": balance, "invested_amount": 5000}]}, "EPF")
    assert rows == [] and "missing or invalid account balance" in warnings[0]


def test_pf_zero_balance_and_unknown_contributions_remain_explicit():
    rows, warnings = normalize({"holdings": [{"investment": "Provident fund", "market_value": 0}]}, "EPF")
    assert warnings == []
    assert rows[0]["market_value"] == "0E-10" and rows[0]["invested_amount"] is None


@pytest.mark.parametrize("timestamp", ["private-invalid-timestamp", "2026-11-08T10:00:00", "2999-01-01T00:00:00Z"])
def test_pf_invalid_dates_are_reported_without_echoing_provider_values(timestamp):
    rows, warnings = normalize({"holdings": [{"investment": "Provident fund", "market_value": 50, "as_of": timestamp}]}, "EPF")
    assert rows == []
    assert warnings == ["Row 1: skipped because invalid balance timestamp."]


def test_duplicate_unidentifiable_pf_accounts_fail_closed():
    with pytest.raises(provider.IndmoneyError, match="indistinguishable PF accounts"):
        normalize({"holdings": [{"investment": "Provident fund", "market_value": 50}] * 2}, "EPF")


def test_pf_preview_sync_ownership_and_repeat_import(indmoney, monkeypatch):
    client, user, portfolio, headers, session, settings, requests = indmoney
    authorize(indmoney)

    async def read(*args):
        return {"result": json.dumps({"holdings": [{"investment": "Employee provident fund",
            "investment_code": None, "asset_type": "EPF", "total_units": None,
            "invested_amount": 5000, "market_value": 5500}]})}

    monkeypatch.setattr(provider, "read_holdings", read)
    path = f"/integrations/indmoney/portfolios/{portfolio.id}"
    assert client.get(path + "/balances", headers=headers).json() == []
    for expected in ("added", "updated"):
        preview = client.post(path + "/preview", headers=headers, json={"asset_type": "EPF"})
        assert preview.status_code == 200, preview.text
        assert preview.json()["rows"][0]["kind"] == "balance"
        result = client.post(path + "/sync", headers=headers, json={"preview_id": preview.json()["preview_id"]})
        assert result.status_code == 200, result.text
        assert result.json()[expected] == 1
    balances = client.get(path + "/balances", headers=headers)
    assert balances.status_code == 200, balances.text
    assert len(balances.json()) == 1
    assert balances.json()[0]["display_name"] == "Employee provident fund"
    assert balances.json()[0]["market_value"] == "5500.0000000000"
    assert balances.json()[0]["as_of"] is None
    assert balances.json()[0]["imported_at"] is not None
    assert client.get(f"/portfolios/{portfolio.id}/holdings", headers=headers).json() == []
    assert client.get(path + "/balances").status_code == 401
    other = User(email="pf-other@example.com", password_hash="unused")
    session.add(other); session.flush()
    other_portfolio = Portfolio(user_id=other.id, name="Other", base_currency="INR")
    session.add(other_portfolio); session.commit()
    assert client.get(f"/integrations/indmoney/portfolios/{other_portfolio.id}/balances", headers=headers).status_code == 404
    assert client.delete("/integrations/indmoney", headers=headers).status_code == 204
    assert len(client.get(path + "/balances", headers=headers).json()) == 1


def test_import_requires_owner_and_live_preview_disconnect_erases_secrets(indmoney, monkeypatch):
    client, user, portfolio, headers, session, settings, requests = indmoney
    authorize(indmoney)
    async def read(*args):
        return {"holdings": [{"symbol": "INFY", "units": "1", "invested_amount": "100"}]}
    monkeypatch.setattr(provider, "read_holdings", read)
    other_user = User(email="indmoney-other@example.com", password_hash="unused")
    session.add(other_user); session.flush()
    other = Portfolio(user_id=other_user.id, name="Other", base_currency="INR")
    session.add(other); session.commit()
    assert client.post(f"/integrations/indmoney/portfolios/{other.id}/preview", headers=headers, json={"asset_type": "IND_STOCK"}).status_code == 404
    path = f"/integrations/indmoney/portfolios/{portfolio.id}"
    preview = client.post(path + "/preview", headers=headers, json={"asset_type": "IND_STOCK"}).json()
    stored = session.get(IndmoneyPreview, UUID(preview["preview_id"]))
    stored.expires_at = provider.now() - timedelta(seconds=1); session.commit()
    assert client.post(path + "/sync", headers=headers, json={"preview_id": preview["preview_id"]}).status_code == 409
    assert client.delete("/integrations/indmoney", headers=headers).status_code == 204
    assert session.scalar(select(IndmoneyConnection).where(IndmoneyConnection.user_id == user.id)) is None
    assert session.scalar(select(IndmoneyPreview).where(IndmoneyPreview.user_id == user.id)) is None
    assert client.post(path + "/sync", headers=headers, json={"preview_id": preview["preview_id"]}).status_code == 409


def test_sdk_discovers_schema_and_calls_only_holdings(monkeypatch):
    calls = []
    @asynccontextmanager
    async def transport(*args, **kwargs):
        yield (None, None, None)
    class Session:
        def __init__(self, *args): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def initialize(self): pass
        async def list_tools(self):
            return SimpleNamespace(tools=[SimpleNamespace(name="networth_holdings", inputSchema={"properties": {
                "asset_type": {"enum": ["IND_STOCK", "MF"]}}, "required": ["asset_type"]})])
        async def call_tool(self, name, arguments):
            calls.append((name, arguments))
            return SimpleNamespace(isError=False, structuredContent={"holdings": []})
    monkeypatch.setattr(provider, "streamable_http_client", transport)
    monkeypatch.setattr(provider, "ClientSession", Session)
    assert asyncio.run(provider.read_holdings("token"))["asset_types"] == ["IND_STOCK", "MF"]
    assert asyncio.run(provider.read_holdings("token", "MF")) == {"holdings": []}
    assert calls == [("networth_holdings", {"asset_type": "MF"})]
    with pytest.raises(provider.IndmoneyError):
        asyncio.run(provider.read_holdings("token", "WRITE"))
