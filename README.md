# AI Investment Research & Portfolio Copilot

An explainable portfolio research application. It combines deterministic portfolio calculations, sourced financial data, document retrieval, and bounded AI workflows. It is a research and risk-analysis aid, not an automated investment adviser.

## Local setup

The initial architecture and implementation sequence are in [docs/architecture.md](docs/architecture.md). The daily execution plan is in `outputs/roadmap/AI_Investment_Copilot_Project_Plan.xlsx`.

Copy `.env.example` to `.env`, then start the local PostgreSQL/pgvector service from the repository root:

```powershell
Copy-Item .env.example .env
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

Start the frontend in a second PowerShell window after installing Node.js (Node 20.19+ or 22.12+):

```powershell
cd frontend
Copy-Item .env.example .env.local
npm install
npm run dev
```

Open `http://127.0.0.1:5173`. The frontend checks `GET /health` on startup. Sign in or create an account, then create a portfolio and import a UTF-8 CSV using the supplied template. The dashboard and portfolio page show backend-calculated cost basis, asset/sector allocation, position rows, and price freshness. Market value and P/L remain blank until usable prices are supplied through the analytics API. Set `VITE_API_BASE_URL` in `frontend/.env.local` to point at another API host; add its frontend origin to `CORS_ORIGINS` in the root `.env` when it differs from the local defaults. Company research remains an explicit empty state until authorized data sources are connected.

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

## Current scope

Days 1–12 provide the architecture and source-access findings, service health endpoint, typed configuration, local PostgreSQL/pgvector setup, user/portfolio/instrument/holding schema and migrations, token authentication, user-scoped portfolio and holdings APIs, CSV import validation, deterministic portfolio analytics, an authenticated analytics endpoint, a React/TypeScript UI with account sign-in, portfolio creation, CSV import, calculated summaries and allocation views, and a typed financial-data provider interface with authenticated lookup routes and explicit unavailable states. The provider review and remaining authorization gate are documented in [docs/data_sources.md](docs/data_sources.md); no live vendor is enabled until its terms cover the app's display and storage. Manual prices remain supported. RAG, MCP integration, company research UI, and a licensed vendor adapter remain subsequent work. The app does not return sample investment figures or connect to a broker account.
