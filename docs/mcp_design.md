# Read-only MCP boundary

The separate `backend/mcp_server/server.py` process uses the official Python MCP SDK, pinned to its supported v1 API. It exposes four typed tools: `list_portfolios`, `portfolio_summary`, `search_research` and `company_profile`. Each has read-only, non-destructive tool annotations. Calls delegate to the application's authenticated HTTP services; there are no transaction, shell, arbitrary URL or file tools.

For a trusted desktop client, run the project Python executable with `-m mcp_server.server` from `backend/`. Supply `COPILOT_API_URL` and the signed-in user's short-lived `COPILOT_MCP_TOKEN` through process environment, never through model arguments. The local stdio client must be trusted because it owns that environment. Each tool request is authorized by the API; object IDs cannot choose another user's identity. Expired tokens fail at the API. STDOUT is reserved for MCP; SDK logs use STDERR.

`GET /mcp/tools` and `POST /mcp/invoke` authenticate the caller, spawn only the fixed local module, pass the caller's token to its environment, initialize the SDK session, discover/invoke tools, and close the process. The backend allowlist prevents arbitrary tool names. There is a 20-second overall timeout and 10-second HTTP timeout. `INTERNAL_API_URL` is operator configuration, never user input. It must point to the same API instance. Server errors return safe categories rather than credential-bearing exception details. MCP tools that calculate metrics or search use POST for read-only queries.

The review graph and chat share the same authorized service functions directly to avoid creating an MCP subprocess for each internal retrieval. MCP is the tested external-client boundary, not a required indirection for local calculations.

INDmoney remains disabled under the existing decision in [data_sources.md](data_sources.md). No vendor client registration, OAuth consent, token or storage permission is assumed. CSV works independently of brokerage access.

Official API references: [Python SDK v1](https://py.sdk.modelcontextprotocol.io/v1/), [SDK source and version policy](https://github.com/modelcontextprotocol/python-sdk/tree/v1.x). New deployments should review v2 migration separately rather than mixing incompatible API examples.
