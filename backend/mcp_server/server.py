"""Official SDK stdio server. Identity comes from a process-scoped bearer token."""
import os
import logging
from uuid import UUID
import httpx
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from app.schemas.research import SearchRequest
from app.schemas.research import Evidence, DocumentRead
from app.schemas.portfolio import PortfolioRead
from app.analytics.models import PortfolioAnalytics
from pydantic import BaseModel


class PortfolioList(BaseModel):
    portfolios: list[PortfolioRead]


class SearchResults(BaseModel):
    evidence: list[Evidence]


class CompanyLookup(BaseModel):
    symbol: str
    exchange: str
    profile: dict
    price: dict
    financial_trends: list[dict]
    trend_status: str
    trend_note: str
    documents: list[DocumentRead]

mcp = FastMCP("Investment Copilot (read only)")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)


async def api(path, method="GET", body=None):
    token = os.environ.get("COPILOT_MCP_TOKEN", "")
    if not token:
        raise ValueError("A process-scoped COPILOT_MCP_TOKEN is required.")
    base = os.environ.get("COPILOT_API_URL", "http://127.0.0.1:8000")
    async with httpx.AsyncClient(base_url=base, timeout=10, follow_redirects=False, trust_env=False) as client:
        response = await client.request(method, path, json=body, headers={"Authorization": f"Bearer {token}"})
        if response.status_code >= 400:
            raise ValueError(f"Copilot API returned HTTP {response.status_code}.")
        return response.json()


@mcp.tool(annotations=READ_ONLY, structured_output=True)
async def list_portfolios() -> PortfolioList:
    """List only the signed-in user's portfolios."""
    return PortfolioList(portfolios=await api("/portfolios"))


@mcp.tool(annotations=READ_ONLY, structured_output=True)
async def portfolio_summary(portfolio_id: UUID) -> PortfolioAnalytics:
    """Calculate a user-owned portfolio's metrics using saved manual prices."""
    return PortfolioAnalytics.model_validate(await api(f"/portfolios/{portfolio_id}/analytics", "POST", {}))


@mcp.tool(annotations=READ_ONLY, structured_output=True)
async def search_research(request: SearchRequest) -> SearchResults:
    """Search only the signed-in user's uploaded research with bounded filters."""
    return SearchResults(evidence=await api("/documents/search", "POST", request.model_dump(mode="json")))


@mcp.tool(annotations=READ_ONLY, structured_output=True)
async def company_profile(symbol: str, exchange: str) -> CompanyLookup:
    """Read cached company profile/price provenance or explicit unavailable states."""
    import re
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,32}", symbol) or not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", exchange):
        raise ValueError("Invalid company identifiers.")
    return CompanyLookup.model_validate(await api(f"/companies/{symbol}?exchange={exchange}"))


if __name__ == "__main__":
    mcp.run(transport="stdio")
