# AI Investment Research & Portfolio Copilot

An explainable portfolio research application. It combines deterministic portfolio calculations, sourced financial data, document retrieval, and bounded AI workflows. It is a research and risk-analysis aid, not an automated investment adviser.

## Local setup

For the complete local application, start Docker Desktop and run `docker compose up -d --build` from this directory. Open **http://127.0.0.1:8080**. The backend applies migrations automatically. Keep your existing `.env`; use `.env.example` only when setting up a new environment.

The remaining roadmap workflows are now implemented: cached provider provenance, manual price entry, private PDF ingestion and hybrid retrieval, page citations, a typed read-only MCP server/client, a bounded LangGraph review, saved reports, portfolio-aware extractive chat, deletion controls, tests, and container deployment. See [acceptance and remaining gates](docs/acceptance.md), the [demo guide](docs/demo_guide.md), [research pipeline](docs/rag_pipeline.md), [MCP design](docs/mcp_design.md), and [interview guide](docs/interview_guide.md).

The default path runs without model/API keys. It uses lexical vectors and quoted source passages. Licensed market feeds, INDmoney access, and optional local semantic/reranking models require separate provisioning; they are not reported as connected.

The initial architecture and implementation sequence are in [docs/architecture.md](docs/architecture.md). The daily execution plan is in `outputs/roadmap/AI_Investment_Copilot_Project_Plan.xlsx`.

For native development, create `.env` only if it is missing, then start the local PostgreSQL/pgvector service from the repository root:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose up -d db
```

Start the FastAPI service from PowerShell:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/health` for the liveness response and `http://127.0.0.1:8000/docs` for the API schema.

Start the frontend in a second PowerShell window after installing Node.js 24+:

```powershell
cd frontend
Copy-Item .env.example .env.local
npm install
npm run dev
```

Open `http://127.0.0.1:5173`. The frontend checks `GET /health` on startup. Sign in or create an account, then create a portfolio and import a UTF-8 CSV using the supplied template. The dashboard and portfolio page show backend-calculated cost basis, asset/sector allocation, position rows, and price freshness. Market value and P/L remain blank until usable prices are supplied through the analytics API. Set `VITE_API_BASE_URL` in `frontend/.env.local` to point at another API host; add its frontend origin to `CORS_ORIGINS` in the root `.env` when it differs from the local defaults. Company research supports uploaded PDFs and cited search; provider facts remain unavailable until an authorized source is connected.

Install `requirements-dev.txt` and run `python -m pytest` from `backend/` to run the CSV and analytics checks.

The app loads typed settings from environment variables (or the root `.env` file), creates its SQLAlchemy engine during application startup, and disposes it during shutdown. `/health` remains a process liveness check and does not require a database connection.

After starting PostgreSQL, apply the initial schema migration from the backend directory:

```powershell
cd backend
alembic upgrade head
```

The API now supports registration and login at `/auth/register` and `/auth/login`. Send the returned bearer token to `/auth/me` and the protected `/portfolios` and `/portfolios/{portfolio_id}/holdings` endpoints. Portfolio and holding reads and writes are scoped to the authenticated user. Configure a strong `SECRET_KEY` before running outside local development.

Holdings can be imported with `POST /portfolios/{portfolio_id}/holdings/import` as multipart field `file`; use [the CSV template](sample_data/holdings_template.csv). The importer accepts UTF-8 CSV files up to 1 MB and 500 rows. Valid rows are saved while invalid or duplicate rows are returned with CSV row numbers. This is a manual file import, not a live broker feed.

`POST /portfolios/{portfolio_id}/analytics` returns cost basis, market value, unrealized P/L, allocation, asset/sector mix, and concentration metadata. Provide optional manual prices as `{"prices":[{"symbol":"INFY","exchange":"NSE","price":"1600.00","currency":"INR","as_of":"2026-11-03T10:00:00Z"}]}`. Without a matching fresh price, market totals and allocation remain incomplete. Prices older than seven days or without an as-of timestamp are excluded from aggregate market metrics. There is no price provider or FX conversion yet.

## Foundation history

Days 1–12 established authentication, portfolio/holding management, CSV imports, Decimal analytics, the dashboard, and the no-provider contract. Subsequent implementation and verification are tracked in [docs/acceptance.md](docs/acceptance.md). The source-access decision in [docs/data_sources.md](docs/data_sources.md) still applies: no live vendor is enabled until its terms cover the app's display and storage.
