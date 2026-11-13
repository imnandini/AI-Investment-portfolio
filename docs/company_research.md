# Company financial research

Set `COMPANY_RESEARCH_PROVIDER=yahoo` in the root `.env`, then rebuild the backend/frontend with `docker compose up -d --build backend frontend`. Use `none` to disable. This setting is independent of automatic daily prices. No API key is required. This is an unofficial personal-use integration, not a licensed commercial data feed.

In **Research → Company lookup**, enter a public company name or ticker, search, and confirm the company and exchange. Search currently covers Indian NSE/BSE equities. You can also paste `https://www.screener.in/company/AARTIIND/consolidated/`. A Screener link is parsed locally to identify the ticker: six-digit codes map to BSE, other company codes to NSE. The provider must verify the resolved ticker, exchange, equity type and INR quote currency before showing a snapshot.

**Research** beside a saved holding pre-fills its company name. A known NSE/BSE ticker offers **Show holding details**. Internal INDmoney references, ISINs and PF account references are not sent as company-search queries. Name searches return candidates for explicit selection; no fuzzy result silently changes a holding.

Available metrics include market capitalisation, trailing P/E, price/book, trailing ROE, net profit margin, revenue, net income, total debt, cash, operating cash flow, free cash flow and EPS. Annual/quarterly income statements, annual balance sheets and annual cash flow show up to four period-end dates each. Provider coverage varies. No figures are invented when a cell, table or currency is unavailable. INR amounts display in crore, percentages display in percentage points and EPS remains INR per share. Negative cash flows and zero values remain intact.

The view labels fetched time separately from quote time and financial reporting dates. Market prices can be delayed. A fetched snapshot is not proof of current financial results. TTM denotes trailing twelve months, and Yahoo reporting periods/basis may differ from Screener's consolidated figures. ROCE, detailed shareholding, report footnotes, auditor commentary and comprehensive risk analysis are outside this snapshot. Original filings remain necessary for those questions.

Public snapshots are cached in `data_source_records` for six hours, keyed by provider, symbol and exchange. Provider failures are cached for one minute. An expired success is replaced with an unavailable result after a failed request. At most two provider jobs run at once, with a twenty-second response budget and no unbounded work queue. Only public search terms/tickers leave the app; portfolio quantities, costs and private documents are not sent.

These research snapshots do not update holdings, valuation prices, private document retrieval, portfolio chat or saved review evidence. The existing licensed-provider endpoints and MCP company profile contract remain unchanged. **Compare on Screener** and **View Yahoo Finance source** open the respective sites separately.

Authenticated API endpoints:

- `GET /companies/search?q=Aarti%20Industries` — candidate names and exchanges, with available/unavailable status.
- `GET /companies/AARTIIND/snapshot?exchange=NSE` — sourced snapshot, cache/fetch dates, metrics, statements and coverage notes.

Sources: [yfinance search documentation](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Search.html), [yfinance company/financial statements](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.html), [Screener API/export guidance](https://support.screener.in/article/28-export-screen-results), [Screener terms](https://www.screener.in/guides/terms/).
