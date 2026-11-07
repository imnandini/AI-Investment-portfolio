import asyncio
import os
from pathlib import Path
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ALLOWED_TOOLS = {"list_portfolios", "portfolio_summary", "search_research", "company_profile"}


async def local_mcp(token: str, api_url: str, name: str | None = None, arguments: dict | None = None):
    if name is not None and name not in ALLOWED_TOOLS:
        raise ValueError("Tool is not in the read-only allowlist.")
    params = StdioServerParameters(command=sys.executable, args=["-m", "mcp_server.server"],
        cwd=str(Path(__file__).resolve().parents[2]),
        env={**os.environ, "COPILOT_MCP_TOKEN": token, "COPILOT_API_URL": api_url})
    async with asyncio.timeout(20):
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                if name is None:
                    tools = await session.list_tools()
                    return [tool.model_dump(mode="json") for tool in tools.tools]
                result = await session.call_tool(name, arguments or {})
                return result.model_dump(mode="json")
