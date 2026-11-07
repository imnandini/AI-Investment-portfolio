from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.middleware.security import SecurityMiddleware
from app.models.portfolio import Portfolio
from app.models.user import User
from app.core.config import Settings
from app.core.security import create_access_token


def test_limits_headers_and_log_privacy(caplog):
    app = FastAPI()
    app.add_middleware(SecurityMiddleware, limit=2)
    @app.get("/items/{item_id}")
    def read(item_id: str):
        return {"ok": True}
    with TestClient(app) as client, caplog.at_level("INFO", logger="copilot.requests"):
        response = client.get("/items/private-record?secret=my-secret", headers={"Authorization": "Bearer my-token"})
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["cache-control"] == "no-store"
        assert client.get("/items/another").status_code == 200
        assert client.get("/items/another").status_code == 429
    logs = " ".join(r.message for r in caplog.records if r.name == "copilot.requests")
    assert "my-secret" not in logs and "my-token" not in logs and "private-record" not in logs
    assert "/items/{item_id}" in logs


def test_registration_login_and_cross_user_writes(api_context):
    client, owner, portfolio, headers, session = api_context
    assert client.post("/auth/register", json={"email": "new@example.com", "password": "long-test-password"}).status_code == 201
    login = client.post("/auth/login", json={"email": "new@example.com", "password": "long-test-password"})
    assert login.status_code == 200
    other_headers = {"Authorization": "Bearer " + login.json()["access_token"]}
    assert client.get("/auth/me", headers=other_headers).json()["email"] == "new@example.com"
    assert client.patch(f"/portfolios/{portfolio.id}", headers=other_headers, json={"name": "Stolen"}).status_code == 404
    assert client.post(f"/portfolios/{portfolio.id}/reviews", headers=other_headers).status_code == 404
    assert client.post("/mcp/invoke", headers=headers, json={"name": "execute_trade", "arguments": {}}).status_code == 422
    assert client.get("/documents").status_code == 401


def test_account_deletion_revokes_access_and_cascades_owned_data(api_context):
    from tests.test_research import upload
    from sqlalchemy import func, select
    from app.models.document import Document
    from app.models.document_chunk import DocumentChunk
    client, owner, portfolio, headers, session = api_context
    upload(client, headers)
    assert client.delete("/auth/me", headers=headers).status_code == 204
    assert client.get("/auth/me", headers=headers).status_code == 401
    assert session.scalar(select(func.count()).select_from(Document)) == 0
    assert session.scalar(select(func.count()).select_from(DocumentChunk)) == 0
