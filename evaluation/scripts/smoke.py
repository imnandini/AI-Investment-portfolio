"""Real HTTP/PostgreSQL and official-SDK stdio MCP acceptance checks."""
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from uuid import uuid4
import httpx
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.integrations.mcp_client import local_mcp


async def run():
    base = "http://127.0.0.1:8000"
    checks = {}
    with httpx.Client(base_url=base, timeout=30, trust_env=False) as api:
        email = f"synthetic-smoke-{uuid4().hex}@example.com"
        password = "synthetic-smoke-password-only"
        api.post("/auth/register", json={"email": email, "password": password}).raise_for_status()
        token = api.post("/auth/login", json={"email": email, "password": password}).json()["access_token"]
        api.headers["Authorization"] = "Bearer " + token
        try:
            portfolio = api.post("/portfolios", json={"name": "SYNTHETIC smoke portfolio", "base_currency": "INR"}).json()
            prefix = f"/portfolios/{portfolio['id']}"
            response = api.post(prefix + "/holdings/import", files={"file": ("synthetic.csv", (ROOT / "sample_data/synthetic_holdings.csv").read_bytes(), "text/csv")})
            response.raise_for_status(); assert response.json()["imported_count"] == 1
            checks["csv_import"] = True
            response = api.post("/documents", files={"file": ("synthetic.pdf", (ROOT / "sample_data/synthetic_report.pdf").read_bytes(), "application/pdf")}, data={"metadata": json.dumps({"title": "SYNTHETIC smoke report", "company": "AAA", "kind": "annual_report", "period": "FY2026"})})
            response.raise_for_status(); assert response.json()["status"] == "ready"
            checks["postgres_pdf_vector_index"] = True
            result = api.post("/documents/answer", json={"query": "revenue", "company": "AAA"})
            result.raise_for_status(); assert result.json()["evidence"][0]["page"] == 1
            checks["postgres_hybrid_retrieval"] = True
            now = datetime.now(timezone.utc).isoformat()
            response = api.put(prefix + "/prices", json={"symbol": "AAA", "exchange": "NSE", "currency": "INR", "price": "125", "as_of": now})
            response.raise_for_status()
            assert api.post(prefix + "/analytics", json={}).json()["market_value_total"] == "250.00"
            checks["persisted_price_analytics"] = True
            review = api.post(prefix + "/reviews"); review.raise_for_status()
            assert review.json()["report"]["evidence"]
            assert api.get(prefix + "/reviews/" + review.json()["id"]).json()["report"] == review.json()["report"]
            checks["review_graph_history"] = True
            tools = await local_mcp(token, base)
            assert {t["name"] for t in tools} == {"list_portfolios", "portfolio_summary", "search_research", "company_profile"}
            assert all(t["annotations"]["readOnlyHint"] and t.get("outputSchema") for t in tools)
            checks["mcp_discovery_typed_read_only"] = True
            for name, arguments in [("list_portfolios", {}), ("portfolio_summary", {"portfolio_id": portfolio["id"]}), ("search_research", {"request": {"query": "revenue", "company": "AAA"}}), ("company_profile", {"symbol": "AAA", "exchange": "NSE"})]:
                result = await local_mcp(token, base, name, arguments)
                assert not result["isError"], name
                checks["mcp_" + name] = True
            result = await local_mcp(token, base, "portfolio_summary", {"portfolio_id": str(uuid4())})
            assert result["isError"]
            checks["mcp_object_access_denied"] = True
            result = api.get("/mcp/tools"); result.raise_for_status()
            assert len(result.json()) == 4
            checks["backend_mcp_client_route"] = True
        finally:
            response = api.delete("/auth/me")
            response.raise_for_status()
            checks["disposable_account_deleted"] = True
    report = {"measured_at": datetime.now(timezone.utc).isoformat(), "scope": "real Docker PostgreSQL/pgvector + HTTP API + official MCP SDK stdio", "checks": checks}
    path = ROOT / "evaluation/reports/deployment_smoke.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(run())
