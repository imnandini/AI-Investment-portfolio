# Northstar — AI Investment Research & Portfolio Copilot

A private workspace for understanding your investments. Connect INDmoney or import a CSV, see your holdings by company name, explore recent stock news, and build a clearer view of portfolio concentration and risk.

The application combines exact portfolio calculations, public news, private document retrieval and a bounded LangGraph review workflow. Its default research path works without a paid news account or model API key. Research views explain their evidence and limitations; the app does not execute trades or generate personalized buy/sell instructions.

## What you can do

| Feature | What it gives you |
| --- | --- |
| INDmoney connection | Read-only account sign-in, a named holdings preview, and an incremental import of the positions you review. |
| Stocks and mutual funds | Quantities, recorded purchase cost, automatic daily stock closes when enabled, saved provider prices, and explicit price freshness. |
| Daily portfolio tracking | Dated Yahoo Finance closing-price history, automatic refresh and day/week comparisons for the current holdings. No daily manual entry or broker login. Personal-use opt-in. |
| EPF and PPF | Reported account balances and invested amounts in a separate **PF balances** section. |
| CSV import | A downloadable template, row-level validation, and support for up to 500 rows per file. |
| Stock briefs | One-click **Pros, cons & news**: recent headlines, source-linked signals, why they matter, what to check next, and the holding's portfolio context. |
| Portfolio opinion | A one-click view of single-name concentration, known sector exposure, missing data and company news. |
| Private document research | Upload company reports, search relevant passages, and inspect page-level citations and original source links. |
| Saved portfolio reviews | A bounded LangGraph workflow that assesses all holdings, checks recent news for up to 20 largest listed holdings, adds optional document evidence and saves a source-linked report with explicit coverage. |
| Portfolio chat | Ask about overall portfolio health, allocation, saved gain/loss and recent company news. Uploaded documents are optional extra evidence. |
| Read-only MCP | Typed tools for application research workflows, plus a separate official INDmoney connection. |

The interface uses navy navigation, teal accents, larger body text, clear metric cards and responsive layouts. Briefs include fuller explanations and a practical reading plan. Reported facts, calculation-based observations and missing inputs remain distinguishable.

## Run the complete app

Start Docker Desktop, then run these commands from the repository root in PowerShell:

```powershell
# Create a local configuration only if you do not already have one.
if (-not (Test-Path .env)) { Copy-Item .env.example .env }

# Optional: prepare the private local encryption key for INDmoney.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/setup-indmoney.ps1

docker compose up -d --build
```

Open **http://127.0.0.1:8080**. Create an account or sign in, then open **Portfolios**. The backend applies database migrations during startup. Keep an existing `.env` and its INDmoney encryption key stable across rebuilds.

### Email verification setup

Email verification can be paused with `EMAIL_VERIFICATION_REQUIRED=false` in the root `.env`. In that mode, registration still requires matching passwords and offers show/hide buttons, then signs the user in without sending email. Existing accounts can also sign in. Accounts are not marked email-verified. To resume verification, configure SMTP and set `EMAIL_VERIFICATION_REQUIRED=true`, then rebuild/restart the backend and frontend. Verification is required by default.

Registration requires matching password and confirmation fields (12–128 characters). Both fields are masked initially and have independent show/hide buttons. After registration, enter the six-digit code sent to your email before accessing the app. Codes expire after 10 minutes, allow five attempts, and can be resent after 60 seconds. Existing accounts also need to verify their email on their next sign-in; select **Send a new code** when prompted. Unverified accounts cannot use portfolio APIs, including with previously issued tokens.

Configure the sending mailbox in the root `.env` before starting the updated backend:

```dotenv
SMTP_HOST=smtp.your-provider.com
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_USERNAME=your-sending-email@example.com
SMTP_PASSWORD=your-provider-smtp-password
SMTP_FROM_EMAIL=your-sending-email@example.com
```

Use the SMTP details supplied by your email provider. `SMTP_FROM_EMAIL` must be an address your provider permits you to send from. Providers may require an app password or a dedicated SMTP credential. For implicit TLS use `SMTP_SECURITY=ssl` and the provider's port (usually 465). Connections verify TLS certificates. Credentials stay in the ignored `.env` file. Docker Compose passes these settings to the backend; after changes run `docker compose up -d --build backend frontend` (or restart the native backend).

Missing settings or failed delivery produce a clear error and keep registration retryable. Codes are never included in API responses or application logs; only a keyed code hash is stored. SMTP delivery must be tested with your actual provider before relying on it for sign-ups.

Useful local endpoints:

| Address | Purpose |
| --- | --- |
| `http://127.0.0.1:8080` | Application |
| `http://127.0.0.1:8000/health` | Backend process liveness |
| `http://127.0.0.1:8000/docs` | Interactive API schema |

`/health` checks the API process; it does not establish database, broker or news-provider availability. Service status is available with `docker compose ps`.

## Your first portfolio

1. Create or select a portfolio in **Portfolios**.
2. Choose **Connect INDmoney**, complete sign-in and consent on INDmoney's own site, and return to the app.
3. Select **Indian stocks**, **US stocks** or **Mutual funds**, then click **Preview holdings**.
4. Review the named positions and import notes, then click **Import reviewed holdings**. Previewing alone does not save positions.
5. Repeat with **EPF** or **PPF** to add provident-fund account balances. Each import covers only the selected asset type.
6. Click **Pros, cons & news** beside a saved stock, or **Portfolio opinion** above the holdings.

You can also use **Import CSV** with [the holdings template](sample_data/holdings_template.csv). Required columns are `symbol`, `quantity` and `average_cost`. Optional columns include exchange, asset type, currency, sector and purchase date.

### INDmoney import behavior

- Imports add new positions and refresh matching INDmoney positions. Repeating an import does not keep adding the same quantity.
- Existing manual/CSV positions are preserved. Positions absent from a later import are retained; remove closed security positions manually.
- Company names are saved from the provider. Internal INDmoney references remain stable import and research identifiers; they are not assumed to be exchange tickers.
- Missing exchanges appear as **Exchange not supplied**. Prices with no provider timestamp appear as **Price date not supplied**. Missing purchase costs remain unknown.
- EPF/PPF accounts use reported balances. The adapter does not invent stock quantities, unit prices, account dates or gains for these accounts.
- Disconnecting removes local credentials and pending previews while retaining imported positions and balances.

See [INDmoney setup, authentication and sync details](docs/indmoney.md) for callback origins, native development and optional registered-client configuration.

## One-click research

### Stock briefs

**Pros, cons & news** opens a brief on the portfolio page. It includes:

- A short research view summarizing the signals present in recent company-matched headlines.
- Potential positives and concerns, each connected to its supporting source links.
- Explanations of why a topic could matter to the business, with specific checks to make in company disclosures.
- Recent headlines with publisher names, publication dates and the news-check time.
- The holding's known portfolio weight and an explanation of what that weight measures.
- Matching private document excerpts when available, plus a practical reading plan.

Public RSS queries focus on earnings, business, orders, debt and outlook. The adapter uses Bing News RSS with Google News RSS as a fallback, filters routine live-price ticker articles, and returns up to eight company-matched headlines from the last 30 days. News is cached for ten minutes; failures are cached for one minute. **Refresh brief** rechecks the assessment and reuses a current news cache.

These are conservative headline topic signals. Full articles, company identity and business claims are not independently verified by the brief. An empty list of concerns does not establish that a stock is safe. Fundamentals, valuation, analyst consensus and price targets are not supplied by this feature.

### Portfolio opinion

The portfolio view explains the largest security weights, small position counts, known sector concentration and missing prices or sector metadata. Complete fresh market values determine weights when available; otherwise complete recorded cost basis is used and labeled clearly. The view also brings together news for up to ten equity holdings ranked by recorded purchase cost, with unknown costs last.

Single-name weights above 25% and known sector weights above 40% are review prompts, not prescribed allocation limits. PF balances are acknowledged separately and are excluded from security weights. The view does not represent a complete household asset allocation or assess personal suitability.

See [brief sources, methodology, limits and API endpoints](docs/research_briefs.md).

## Ask about your portfolio

Open **Portfolio chat** in the sidebar, or **Ask about holdings** on the portfolio page. Select a portfolio and ask a question; no document upload or model API key is required.

- **Is my overall portfolio okay?** checks security concentration, known sector exposure, missing prices and recent equity news, using the same calculations as Portfolio opinion.
- **What are my companies doing currently?** checks dated public news for up to ten saved equity holdings. Include a company's full saved name or symbol for a focused answer.
- **How much is my portfolio worth?** or **What is my profit?** uses saved holdings and usable dated prices, with missing costs and prices reported explicitly. It does not calculate live quotes or daily/total investment returns.
- **What is diversification?** explains a supported portfolio concept. Questions about uploaded reports still return matching passages with document citations.

Answers retain their portfolio snapshot and news-check dates in chat history. News links show publishers and publication dates; feed failures remain visible. Routing and summaries are rules-based, not an unrestricted conversational model. The checks do not establish personal suitability or a buy/sell decision.

## Deeper research with documents

Use **Research** beside a holding to open its document workspace. The holding reference is prefilled as the document tag and search filter, so matching documents can also be used by portfolio chat and reviews.

Upload text PDFs you are entitled to use, up to 5 MB and 100 pages each. Search answers quote relevant passages with document/page citations. Originals are processed in memory; extracted text and metadata are stored privately. Scanned, encrypted, malformed or unsupported files receive explicit status messages.

**Search web sources** opens an external search. Those pages are not automatically ingested into the private library. Company lookup requires a verified exchange ticker and a configured authorized data provider; an internal INDmoney code is not a verified ticker.

The default retrieval implementation uses lexical/hash vectors and extractive answers. Optional local semantic embeddings and reranking require separately provisioned models. See the [research pipeline](docs/rag_pipeline.md).

## Calculations and data coverage

Portfolio calculations use Decimal arithmetic:

- **Cost basis:** quantity × average purchase cost.
- **Market value:** quantity × a matching supplied or saved price.
- **Unrealized P/L:** market value − cost basis, when both are known.
- **Unrealized return %:** (latest price − average purchase cost) ÷ average purchase cost × 100, with a usable dated price and positive known purchase cost. Each holding shows P/L and return %. The portfolio percentage uses total P/L ÷ total cost, rather than averaging holding percentages. These are cumulative price returns on current holdings, excluding dividends, realized trades, fees and taxes; they are not annualized or total investment returns.
- **Market allocation:** each position's share of complete base-currency market value.
- **Asset/sector mix:** known base-currency cost basis.
- **Concentration index:** sum of squared market-allocation percentages, on a 0–10,000 scale.

Enable `DAILY_PRICE_PROVIDER=yahoo` in the root `.env` for this personal app's automatic daily closes. The app fetches completed bars through yesterday and retains price history. Each holding shows the actual source, date and resolved exchange. Day/week comparisons revalue the current quantities at shared historical closes; they are not total investment returns. See [daily prices, coverage and comparison methodology](docs/daily_prices.md).

Manual reference prices remain available in a collapsed optional section. A newer automatic close replaces an old manual reference; newer dated manual/imported prices can still supply the current valuation. Prices older than seven days, prices with no timestamp, and currency-mismatched prices are excluded from aggregate market metrics. There is no inferred FX conversion, estimated missing price or zero-filled missing purchase cost. PF account balances stay separate from security calculations.

Daily pricing is an unofficial Yahoo/yfinance personal-use integration and can be delayed or unavailable. Company fundamentals/profile lookup still has no licensed provider enabled. Public news availability does not establish complete financial fundamentals or a current valuation.

## Native development

The containers are the simplest complete setup. For native development, install Python and Node.js 24+, keep the root `.env`, and start PostgreSQL/pgvector:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose up -d db

py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements-dev.txt

cd backend
alembic upgrade head
uvicorn app.main:app --reload --no-access-log
```

Ensure `DATABASE_URL` uses the credentials and host port configured for the database. Docker's backend connects to `db:5432`; a native backend connects to the exposed localhost port, which is controlled by `POSTGRES_PORT`.

In a second PowerShell window:

```powershell
cd frontend
if (-not (Test-Path .env.local)) { Copy-Item .env.example .env.local }
npm ci
npm run dev
```

Open **http://127.0.0.1:5173**. For INDmoney in native development, set `INDMONEY_REDIRECT_URI=http://127.0.0.1:5173/portfolios` in the root `.env` and restart the backend. Use that same origin before and after sign-in. Set `VITE_API_BASE_URL` in `frontend/.env.local` when using another API host and include its frontend origin in backend `CORS_ORIGINS`.

### Configuration

| Setting | Purpose |
| --- | --- |
| `DATABASE_URL` | SQLAlchemy PostgreSQL connection string. |
| `SECRET_KEY` | Application token signing; use a strong private value outside local development. |
| `INDMONEY_TOKEN_KEY` | Stable Fernet key for stored OAuth credentials and previews. |
| `INDMONEY_REDIRECT_URI` | Exact portfolio-page callback URL for the frontend origin in use. |
| `FINANCIAL_DATA_PROVIDER` | Defaults to `none`; unsupported adapters report unavailable data. |
| `DAILY_PRICE_PROVIDER` | `yahoo` enables personal-use automatic daily closes; `none` disables new fetches. No key required. |
| `EMBEDDING_PROVIDER` | Defaults to `hash`; optional local model configuration is documented separately. |
| `CORS_ORIGINS` | Frontend origins accepted by the API. |
| `POSTGRES_PORT` | Host port exposed by the local Docker database. |

No model or news API key is required for the default stock briefs, portfolio opinion or extractive research workflow.

Saved reviews also check company news automatically, without requiring uploaded reports. They assess every saved holding and show the scope of their bounded news sample. See [saved portfolio assessments and coverage](docs/portfolio_reviews.md).

## Verification

From the repository root, with the Python environment active:

```powershell
python -m pytest backend/tests -q
```

From `frontend/`:

```powershell
npm test
npm run build
```

Optional browser tests against a running local app:

The complete browser scenario requires `E2E_EMAIL` and `E2E_PASSWORD` for a dedicated account whose email has already been verified. It deletes that disposable account when finished; use no personal or shared account. Without these variables, the scenario is skipped. The HTTP smoke script similarly requires `SMOKE_EMAIL` and `SMOKE_PASSWORD` for a verified disposable account and deletes it afterward. Authentication unit tests use a mocked email transport and cover registration, code validation and delivery failures without sending email.

```powershell
npx playwright install chromium
npm run test:e2e
```

Tests cover authentication and ownership, CSV validation, portfolio arithmetic, unknown costs, INDmoney OAuth/imports, PF balances, source/date filtering, news failure and caching, signal attribution, research retrieval and citations, one-click brief interactions, retries and stale responses. The production build checks TypeScript and bundles the interface.

## Project structure

```text
backend/app/api/                       Authenticated FastAPI endpoints
backend/app/integrations/              INDmoney, company news and provider adapters
backend/app/services/                  Import, pricing and research brief logic
backend/app/analytics/                 Exact portfolio calculations
backend/app/agents/portfolio_review/   Bounded LangGraph review workflow
backend/app/rag/                       Retrieval and extractive answers
backend/migrations/                   Alembic schema migrations
frontend/src/pages/                   Portfolio, dashboard and research screens
frontend/src/components/              Holdings, briefs, sources and account views
frontend/src/theme.css                App-wide palette, type scale and responsive styling
backend/tests/                        Backend regression suite
frontend/src/**/*.test.tsx            Frontend interaction checks
```

## Privacy and application boundaries

Accounts scope portfolios, documents, saved prices, chat and reviews to their owner. INDmoney sign-in takes place on the vendor's own pages; credentials remain encrypted in the backend. News requests send public company names and market locale, not holdings quantities, account balances or purchase costs. Callback logging and external tracing are disabled in the supplied local configuration.

The app is a research and risk-analysis aid. News feeds can be unavailable or incomplete, uploaded sources can conflict, and missing data remains visible. There is no continuous broker reconciliation, automated trading, personalized suitability engine or enabled licensed real-time market feed.

Further documentation: [architecture](docs/architecture.md), [acceptance and remaining gates](docs/acceptance.md), [demo guide](docs/demo_guide.md), [MCP design](docs/mcp_design.md), [data sources](docs/data_sources.md), and [interview guide](docs/interview_guide.md).
