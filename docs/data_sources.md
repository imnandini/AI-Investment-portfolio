# Indian market data and disclosure sources

**Personal-app update — 11 November 2026:** the owner selected Yahoo Finance for automatic daily prices in this local personal app. The opt-in `DAILY_PRICE_PROVIDER=yahoo` integration uses `yfinance`, with no API key or broker login. This supersedes the no-provider decision below only for this personal daily-close path. Company fundamentals/profile lookup remains disabled. This is an unofficial personal-use source, not a licensed feed for commercial redistribution. See [daily pricing](daily_prices.md) and the [yfinance source](https://github.com/ranaroussi/yfinance).

**Decision record — 5 November 2026; provider disabled by product decision — 6 November 2026**
**Status: no market-data provider selected; continue with manual prices and CSV holdings.**

This review supports a single-user research prototype that may become a multi-user product. A documented API and an account holder's access do not by themselves establish the right for this application to store, transform, or display the data to its users. No provider is enabled in the code.

## Decision

Keep the existing manual-price path as the supported no-provider path. It is usable now and does not depend on an unverified vendor license. Do not fetch exchange-site pages or a broker's private endpoints as a substitute.

Upstox is the first broker API to approach for written product-fit clarification because its official developer platform documents NSE/BSE market-data APIs and an integration contact. That makes it a **candidate for commercial review, not a selected provider**. The public pages reviewed do not settle whether a shared application may cache, transform, or display its market data to users who are not the API account holder, nor the required downstream user disclosures and retention rules. Dhan has a documented, low-cost data API for an individual Dhan account, but its published material likewise does not settle multi-user product display rights. NSE and BSE sell data under product-specific agreements and tariffs; a paid subscription must explicitly cover this application's website, mobile, storage, derived analytics, and user population before use.

The NSE MCP service is not a usable shortcut for this commercial/third-party product: NSE's published disclaimer limits its use to informational, non-commercial purposes and says access grants no right to commercially exploit data in third-party applications or AI systems. Use the public filing pages as citation destinations for a human reader; do not automate collection until the applicable website terms or a separate feed agreement permits it.

## Candidate comparison

| Candidate | Coverage and identifiers | Terms, cost, and access | Limits and operational evidence | Decision |
|---|---|---|---|---|
| **Upstox Developer API** | Official docs expose live market quotes, a WebSocket feed, historical data, fundamentals, and news. Instruments use Upstox instrument keys and include NSE/BSE segments. | Upstox advertises its APIs and market data as free. An Analytics Token is read-only, lasts one year, is generated from an Upstox account, and only one is active per account. OAuth is available for user authorization. Its site tells businesses seeking integration to contact `api@upstox.com`. Public docs do not grant or specify the redistribution/display license this product needs. | Feed v3 documents connection and instrument subscription caps. Market data is a live stream; the application would need to map the project's `(symbol, exchange)` to stable provider instrument keys, handle feed timestamps, reconnects, and provider changes. Public docs do not establish an SLA for this use. | **First candidate to ask for written approval and terms; not selected.** A free API price does not answer downstream data rights. |
| **DhanHQ Data APIs** | LTP, OHLC, and quote snapshots cover NSE and BSE exchange segments using Dhan security IDs. WebSocket feed is also documented. | Dhan support currently lists Data APIs at ₹499/month plus applicable taxes, debited from the user's Dhan ledger. Access requires a Dhan account, client ID, and access token. Public materials describe individual account access; no multi-user display/redistribution grant was located. | Market Quote supports up to 1,000 instruments per request at one request per second. Live feed allows up to five connections per user and 5,000 instruments per connection; responses are binary and need parsing. No SLA for this product use was located. | **Not selected.** Promising for a Dhan-account-holder's personal data flow only after reviewing applicable API/data terms; not a shared service credential. |
| **NSE Data & Analytics, direct** | Exchange source for NSE capital-market, F&O, currency, debt, corporate, historical/EOD, snapshot, and real-time products. NSE documents stock-wise, snapshot, delayed, and real-time delivery options. | Access is by product subscription and relevant agreement. The domestic tariff effective 1 April 2026 lists examples including capital-market EOD at ₹1,00,000/year (subject to the product's site/medium terms) and 15-minute delayed capital-market data at ₹1,40,000/year per site; open website/mobile and other products have separate fees. Fees exclude taxes. NSE's policy says the agreement defines intended use, handling, display, transmission, and end-user restrictions; redistribution is allowed only where agreed. | Official technical specifications and product formats are available. Feed delivery can require SFTP or a dedicated circuit/vendor. NSE publishes a list of authorized real-time vendors. The app would need an agreement that explicitly covers its precise delivery, persistence, and derived-metric use. | **Not selected now.** Revisit if a direct commercial subscription and downstream display rights are obtained and budgeted. |
| **BSE Data / Self Data Feed** | BSE's official data portal lists Equity, Equity Derivatives, Corporate Data (financials, disclosures, announcements, actions), Indices OHLC, and delayed data APIs. | The portal requires registration/KYC, choosing a plan, agreeing pricing and agreements, and payment. The public portal does not show a definitive price for this app's exact usage. A BSE tariff PDF dated February 2025 is still published, but may not reflect a November 2026 quote or current portal plan. | BSE describes structured API feeds and limited free trials. Coverage is BSE data; NSE-listed records require a separate source or cross-exchange mapping. Public API limits and service SLA for the intended plan were not established in this review. | **Not selected.** Request a current written quote and explicit website/app, storage, derived analytics, and user rights before implementation. |

Costs and product features above are the public terms observed on the date of this record; they are not a quote or a legal conclusion. A vendor's account access is not evidence that the vendor has licensed onward display to this application.

## Official disclosure and filing routes

| Source | What it provides | Use in this project |
|---|---|---|
| [NSE corporate filings and announcements](https://www.nseindia.com/companies-listing/corporate-filings-announcements) | Exchange-published announcements and issuer filings. The NSE site also links filings, financial results, annual reports, shareholding patterns, and corporate actions. | Link users to the original filing and retain issuer, exchange, filing title, publication date, and canonical source URL when a licensed ingestion route is established. Do not scrape or bulk-download from the public website based only on page availability. |
| [BSE Corporate Announcements](https://www.bseindia.com/corporates/ann) and [BSE Self Data Feed](https://marketdata.bseindia.com/) | BSE issuer announcements/filings and a separately described API catalogue for corporate data, disclosures, and actions. | Prefer the authorized API subscription for automated ingestion. The public page remains a source link; portal KYC, plan, pricing, and agreement need review before connecting it. |
| [NSE Data MCP](https://www.nseindia.com/nse-mcp) | NSE describes its MCP feeds as daily end-of-day and near-real-time delayed by 1–3 minutes, with no tick-by-tick/order-book data. | **Do not use in this product** unless NSE grants permission that supersedes/clarifies the published non-commercial and third-party application restrictions. |

## Conditions to select a provider

Before enabling an adapter, retain the provider's written answers or signed terms covering:

1. The app's named legal entity, customer type, permitted jurisdictions, and whether a multi-user research copilot qualifies.
2. NSE and BSE instrument coverage, identifier files, symbol changes/corporate actions, asset types, timestamps, currency fields, and any gaps.
3. Whether the app may fetch per-user or under a shared account; whether it may persist raw data and for how long; how cache and delete requests work.
4. Whether the app may display raw, delayed, transformed, or aggregated data and analytics to each user; redistribution, derived data, attribution, and end-user contract requirements.
5. Fees at prototype and production scale, user/medium/site definitions, taxes, minimums, rate limits, overage, and plan changes.
6. Authentication lifecycle, secrets/token storage, refresh/revocation, IP allowlisting, service availability/SLA, support, error behavior, and notice of breaking changes.
7. An authorized sandbox or test account, permitted validation data, and a documented go-live approval.

If these conditions remain unresolved, keep provider lookup disabled. The manual price input must continue to label source and as-of time, and missing/stale prices must remain incomplete in analytics.

## Day 12 implementation state

`backend/app/integrations/financial_data/` now defines an async read-only provider port for company profiles and prices, plus a fail-closed `none` adapter. `backend/app/services/financial_data.py` bounds adapter calls with a configurable timeout and converts provider errors, timeouts, and unexpected failures into stable typed unavailable results without returning raw exception text. `GET /financial-data/profile/{symbol}` and `GET /financial-data/price/{symbol}` require the app's bearer authentication and return the typed result. `FINANCIAL_DATA_PROVIDER=none` is the default; unknown/unimplemented provider names return `provider_not_implemented` and make no outbound request. No vendor-specific adapter or credentials are enabled until the provider terms pass the selection conditions above.

## Sources reviewed

Official sources accessed on 5 November 2026:

- [Upstox API overview and business integration contact](https://upstox.com/trading-api/)
- [Upstox Analytics Token announcement](https://upstox.com/developer/api-documentation/announcements/analytics-token/)
- [Upstox authentication](https://upstox.com/developer/api-documentation/authentication/)
- [Upstox Market Data Feed V3](https://upstox.com/developer/api-documentation/v3/get-market-data-feed/)
- [DhanHQ Market Quote](https://dhanhq.co/docs/v2/market-quote/)
- [DhanHQ Live Market Feed](https://dhanhq.co/docs/v2/live-market-feed/)
- [Dhan support: Data API access and current subscription price](https://dhan.co/support/platforms/dhanhq-api/how-to-access-dhan-api/)
- [NSE Data Sharing & Usage Policy](https://www.nseindia.com/static/market-data/nse-data-policy)
- [NSE Products Tariff](https://www.nseindia.com/static/market-data/products-tariff) and [Domestic tariff effective 1 April 2026](https://nsearchives.nseindia.com/web/mediaattachment/2026-04/Download_Pricing_file_-_Domestic_clients_20260424122229.pdf)
- [NSE paid real-time data](https://www.nseindia.com/static/market-data/real-time-data-subscription) and [EOD/historical data](https://www.nseindia.com/static/market-data/eod-historical-data-subscription)
- [BSE Self Data Feed](https://marketdata.bseindia.com/) and [BSE February 2025 information-product tariff](https://www.bseindia.com/downloads1/Information_Products_Pricing_Sheet.pdf)
- [NSE Data MCP terms and limitations](https://www.nseindia.com/nse-mcp)
