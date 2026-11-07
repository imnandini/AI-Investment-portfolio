import asyncio
from mcp_server.server import mcp


def test_tool_discovery_is_typed_and_read_only():
    tools = asyncio.run(mcp.list_tools())
    assert {t.name for t in tools} == {"list_portfolios", "portfolio_summary", "search_research", "company_profile"}
    assert all(t.annotations.readOnlyHint and t.outputSchema and t.inputSchema for t in tools)
