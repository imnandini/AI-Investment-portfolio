# One-click stock and portfolio briefs

On **Portfolios**, import reviewed holdings, then click **Pros, cons & news** beside an equity or **Portfolio opinion** above the metrics. Results open on the same page. No model key, paid news account or document upload is required.

## Sources and interpretation

The backend queries public Bing News RSS, falling back to Google News RSS when the first feed fails or returns no company-matched articles. Only the company name and market locale are sent; holdings, balances, purchase costs and account credentials are not sent. Microsoft describes its news RSS support in [News Search — now with RSS](https://blogs.bing.com/search/April-2008/News-Search-%E2%80%93-now-with-RSS).

Feeds are subject to availability and schema changes; they are not a licensed fundamentals or real-time price API. Queries focus on earnings, business, orders, debt and outlook. The adapter keeps up to eight matching headlines published within the last 30 days, filters routine live-price ticker headlines, rejects undated/future articles, deduplicates titles and preserves publisher, article link, publication date and original fetch time. Matching requires the normalized company phrase in the title; this can miss abbreviated company names. Publisher identity and full article claims are not independently verified. Each feed request has a five-second total limit, does not follow redirects and accepts at most 1 MB. Unsafe XML declarations are rejected.

Public news results are cached in a bounded process-local cache for ten minutes; feed failures are cached for one minute. Refreshing the brief recalculates the portfolio assessment and reuses a still-current news cache. Cache time is visible. Restarting clears this cache. There is no background polling or automatic import of article bodies.

## Stock brief

Conservative headline rules surface reported earnings growth, new orders, debt reduction, earnings pressure, governance/regulatory concerns and financial distress. Denials, negations, forecasts and ambiguous headlines stay neutral. Each signal links to the supporting headline and gives a specific filing check. Empty positives or concerns are not replaced by invented claims. The resulting view summarizes these topics, not company valuation or suitability. Missing news is reported as unavailable or empty, never as a favorable stock verdict.

Matching private document excerpts are also shown when available. The existing **Research** link remains the place to upload documents and ask cited questions. Briefs do not scrape full articles, generate target prices, claim analyst consensus or recommend trades.

## Portfolio opinion

All saved securities contribute to the calculated structure assessment. Complete fresh market values determine weights when available; otherwise complete recorded cost basis is used and explicitly labeled. The assessment flags a single name above 25%, a known sector above 40%, fewer than five security positions, missing sectors and incomplete price coverage. These are review prompts, not prescribed allocation limits. A lower single-name weight does not establish adequate diversification.

News is checked for up to ten equity holdings, ranked by recorded cost basis, with unknown costs last. At most three company requests run concurrently. Database access stays sequential. PF balances are acknowledged separately and do not enter security weights. The result is not a complete household asset allocation or personalized assessment; goals, horizon, tax circumstances and other assets are unknown.

## API and checks

- `POST /portfolios/{portfolio_id}/holdings/{holding_id}/brief`
- `POST /portfolios/{portfolio_id}/brief`

Both endpoints authenticate the user and check portfolio ownership before reading holdings or contacting news feeds. The stock endpoint also verifies that the holding belongs to the selected portfolio and is an equity. Results are generated on demand and do not modify holdings, prices, imports or documents.

Regression tests cover company/date/link filtering, duplicate headlines, malformed/oversized XML, provider fallback and failure, cache timestamps, conservative signal rules, source references, concentration calculations, PF scope, cross-user access, stock/portfolio buttons, rendering, retry and stale-response handling.
