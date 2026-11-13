# INDmoney holdings connection

The portfolio workspace supports an account-scoped, read-only connection to the official `https://mcp.indmoney.com/mcp` server. This is separate from the application's own local stdio MCP server. No language-model API key is needed.

## Run locally

From the repository root in PowerShell:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/setup-indmoney.ps1
docker compose up -d --build
```

The setup script adds a randomly generated Fernet encryption key to the existing, git-ignored `.env` without displaying it or changing other settings. Keep this key stable: replacing it makes stored connections and pending previews unreadable. Never commit it or share it.

Open **http://127.0.0.1:8080/portfolios** and sign in to the copilot. Create or select a portfolio, click **Connect INDmoney**, complete authentication and consent on INDmoney's own page, and return to the portfolio workspace. Select an asset type, click **Preview holdings**, inspect the positions and import notes, then click **Import reviewed holdings**. Repeat preview/import whenever you want to refresh that asset group.

Use the same browser origin before and after sign-in: the default callback is `http://127.0.0.1:8080/portfolios`. For native Vite development set `INDMONEY_REDIRECT_URI=http://127.0.0.1:5173/portfolios` in the root `.env`, restart the backend, and open the frontend at that exact origin. A deployed application needs its HTTPS portfolio URL. The callback uses the signed-in copilot session, browser session state, server-side state validation and PKCE; it does not transfer an application bearer token in a URL.

## Authentication and operations

The backend reads public OAuth protected-resource and authorization-server metadata, validates INDmoney's issuer and endpoints, and requests **only `portfolio:read`**. It registers an application client using the advertised dynamic registration endpoint. If a deployment requires a pre-registered client, configure `INDMONEY_CLIENT_ID` and `INDMONEY_CLIENT_SECRET`. Client authentication supports the advertised secret-post or secret-basic methods. PKCE uses S256. The state expires after ten minutes and is consumed once. Expiring tokens are refreshed when the vendor issued a refresh token; otherwise the user reconnects.

Access/refresh tokens, client secrets, PKCE verifiers and preview contents are encrypted in the database. Tokens stay in the backend. Callbacks arrive at the frontend, which immediately removes code and state from browser history and exchanges them through an authenticated POST. The supplied Nginx configuration disables access logging to avoid recording callback query strings; equivalent proxy logging precautions are needed for other deployments. Backend deployments should retain `--no-access-log`.

The remote SDK client discovers `networth_holdings` and its input schema, and calls only that tool. It does not expose arbitrary tool invocation or request write scopes. Timeouts, upstream errors, invalid formats and incomplete/paginated responses stop the operation with a visible error; they do not silently import a partial snapshot. Public documentation does not include the complete private response schema. The adapter accepts structured JSON holdings/positions/items envelopes with explicit identifiers and quantities; an unfamiliar private schema requires an adapter update rather than inferred values.

## Import behavior

- Previews are scoped to the signed-in user and selected portfolio, encrypted, one-use and valid for ten minutes. Disconnect/reconnect invalidates pending previews.
- Imports add new positions and refresh matching positions previously imported by INDmoney. They do not add the same position repeatedly. An existing manual/CSV holding with the same symbol and exchange is preserved and reported as skipped. Editing an imported holding through the holdings API transfers it to manual control.
- Duplicate positions across brokers are combined by symbol and exchange with a quantity-weighted purchase cost. Missing costs stay unknown. Symbol, ticker, ISIN, scheme-code and INDmoney `investment_code` identifiers are accepted; exchange is `UNKNOWN` when unavailable. The app does not guess a symbol from an instrument name or assume an exchange.
- Missing broker purchase costs are stored as null, never zero. Their holdings still appear, while affected cost basis/P&L and aggregate cost totals remain unavailable. Asset/sector cost figures include known costs only. Unsupported/malformed rows are reported in import notes.
- Imported unit prices are saved with provider timestamps. Without a timestamp they remain of unknown freshness and are excluded from aggregate market metrics. Explicit manual prices take precedence. Currency mismatches and missing FX conversion retain the existing analytics limitations.
- Stock names from INDmoney's `investment` field are saved as display names; its internal code remains the stable import/research reference. Missing exchanges appear as “Exchange not supplied”, and prices without dates appear as “Price date not supplied”. Reimporting enriches existing positions without duplicating them.
- Each security and PF account has a **Research** link that opens the research workspace with that holding's reference, name and question prefilled. Upload documents under the prefilled reference to make them available to matching research and portfolio chat. **Search web sources** opens a web search; web pages are not automatically ingested or used in cited answers. With `COMPANY_RESEARCH_PROVIDER=yahoo`, Indian stock research also supports company-name search and sourced financial snapshots without a PDF. Confirm the company and exchange; internal INDmoney codes are not treated as tickers. See [company research](company_research.md).
- Select **EPF** or **PPF** to preview/import provident-fund accounts. These responses can have a name and reported balance without any security code or units. They are saved as portfolio-scoped account balances and displayed in **PF balances**, with reported invested amounts and dates when supplied. No security quantity, price, timestamp or gain is fabricated. PF balances remain separate from stock/fund analytics and portfolio-review company targets; portfolio chat can search documents tagged with their account reference. Indistinguishable duplicate account names stop the import rather than merging balances by assumption.
- This is an incremental, user-triggered import, not continuous reconciliation. Positions missing from a later response are retained, including closed positions; remove closed positions manually. Import all desired asset groups separately.
- Disconnect deletes local OAuth credentials and previews, retaining imported holdings. Consent can also be revoked from INDmoney settings. Account deletion cascades through the integration records and portfolio data.

## Verification

On 7 November 2026, the real public metadata endpoints responded successfully and INDmoney accepted dynamic client registration for the local callback with HTTP 201. On 8 November 2026, a read-only check using the owner's existing connection verified that the private stock response wraps JSON in `result` and supplies `investment_code`, `asset_type: STOCK`, `total_units`, `invested_amount` and `unit_price`. The adapter uses the requested `IND_STOCK` or `US_STOCK` group to resolve the generic `STOCK` label. Both returned stock holdings normalized without warnings; this diagnostic did not apply an import. Regression fixtures use synthetic values. Automated tests cover PKCE, narrow scopes, encrypted credentials, replay/expiry, token refresh, schema discovery, owner checks, previews, repeated imports, manual conflicts, unknown costs, the provider's stock schema and frontend callback/import/error behavior.

Official references: [INDmoney MCP](https://www.indmoney.com/mcp), [MCP authorization](https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization), [MCP Python SDK v1](https://py.sdk.modelcontextprotocol.io/v1/). This implementation supersedes the earlier local-only INDmoney deferral for this user's requested personal connection. Market-feed licensing and any future multi-user commercial deployment remain separate decisions.
