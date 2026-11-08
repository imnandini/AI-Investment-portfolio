# Architecture and Day 1 Decisions

## Product boundary

The product helps an authenticated user understand their own holdings and inspect supporting evidence. Python owns portfolio calculations and data validation. AI summarizes retrieved evidence and labels uncertainty. The application does not place trades or promise investment outcomes.

## Proposed architecture

- **React + TypeScript + Vite:** dashboard, portfolio editor/import, company research, chat, and saved review views.
- **FastAPI + Pydantic:** HTTP boundary, request validation, authentication dependencies, and application services.
- **SQLAlchemy + Alembic + PostgreSQL/pgvector:** user-scoped relational records, source provenance, financial documents, and vector embeddings.
- **Analytics services:** deterministic allocation, cost basis, P/L, and concentration calculations; missing/stale inputs remain explicit.
- **Financial provider interface:** provider adapters return typed values with source and retrieval timestamps. No provider is selected until API access, coverage, licensing, limits, and cost are checked.
- **Document ingestion and retrieval:** PDF text extraction, metadata-preserving chunks, PostgreSQL full-text/BM25-compatible retrieval, vector similarity, reciprocal-rank fusion, optional cross-encoder reranking, and citations.
- **LangGraph:** bounded portfolio-review state machine that calls deterministic services and retrieval, then synthesizes evidence into a structured report.
- **Separate MCP server + backend MCP client:** typed, read-only portfolio and research operations. FastAPI remains the app's user-facing API; MCP provides tool interoperability.
- **Docker Compose:** local PostgreSQL/pgvector and application services after the minimal local flow is established.

## Data flow

1. A user registers or logs in. An authorization dependency resolves the user identity from a verified session/token; request payloads never establish ownership.
2. CSV import validates file type, size, required columns, values, duplicates, and instrument identifiers. Import errors point to rows and fields. Valid holdings are saved under the authenticated user's portfolio.
3. Portfolio API responses read only rows owned by that user. The analytics service computes values from holdings and available prices; each result carries currency, source, as-of time, and completeness state.
4. A configured provider adapter fetches allowed company/market data. Cache and provenance records keep provider, retrieval time, reporting period, and stale/error state alongside values.
5. Document ingestion validates a PDF, extracts text and page numbers, normalizes and chunks content, hashes it to prevent duplicate ingestion, then stores text, metadata, keyword index content, and embeddings.
6. A research question is scoped to the user's allowed portfolio/company filters. Retrieval combines lexical and vector candidates, fuses and reranks them, then returns passages with document/page citations.
7. The LangGraph review loads holdings, validates data, calculates metrics, selects research targets, retrieves provider facts and document evidence, checks gaps/conflicts, and builds a report with explicit limitations. It stores the report and citations for reopening.
8. React displays results, source dates, calculations, retrieval citations, partial-data states, and workflow status. It does not present hard-coded demo figures as the user's holdings.

## Initial database proposal

| Entity | Main fields and purpose |
|---|---|
| `users` | id, email, password_hash or external identity, created_at; authentication principal. |
| `portfolios` | id, user_id, name, base_currency, created_at, updated_at; owned collection of holdings. |
| `instruments` | id, canonical_symbol, exchange, asset_type, currency, company metadata; shared identifiers. |
| `holdings` | id, portfolio_id, instrument_id, quantity, average_cost, purchase_date, source metadata; user portfolio position. |
| `price_history` | id, instrument_id, price, currency, as_of, provider, retrieved_at; sourced price history. |
| `financial_metrics` | id, instrument_id, metric, value, unit, reporting_period, published_at, source, retrieved_at; sourced structured company facts. |
| `documents` | id, instrument_id, document_type, reporting_period, publication_date, source_uri, content_hash, processing_status, error; ingested filings. |
| `document_chunks` | id, document_id, page_number, chunk_index, text, embedding, metadata; citation-ready search units. |
| `research_sessions` / `research_messages` | session ownership, user questions, assistant response, timestamps; chat history with privacy controls. |
| `portfolio_reviews` | id, portfolio_id, status, created_at, methodology_version, summary; saved workflow reports. |
| `review_findings` / `review_citations` | finding type/text/evidence status and linked source passages; traceable report detail. |
| `data_source_records` | provider, source identifier, fetched_at, status, error category, cache expiry; provenance and reliability. |
| `evaluation_runs` | dataset/version, metric results, latency, token/cost metadata; reproducible evaluation history. |

Ownership indexes and foreign keys are required. Every user-facing query filters by authenticated owner. Shared instrument/document data is separated from user-specific holdings and reports. Add tables and migrations incrementally when the corresponding feature is implemented.

## External services and access checks

| Need | Planned interface | Day 1 status |
|---|---|---|
| Indian company profiles, prices, statements, quarterly results, news | Provider adapter; select after checking official terms, coverage, exchange identifiers, API limits, cost, and redistribution rights | Unselected; do not invent availability or use silently substituted values. |
| Indian exchange/company disclosures | Source links and document metadata in ingestion/provider records | Required evidence category; source endpoints and permissions to validate per source. |
| LLM and embeddings | Configurable provider interfaces, secrets in environment variables | Provider/model not selected; no keys required for Day 1. |
| PostgreSQL + pgvector | Docker Compose service and SQLAlchemy integration | Planned, not yet provisioned. |
| INDmoney portfolio MCP | Official endpoint shown as `https://mcp.indmoney.com/mcp`; read-only, Streamable HTTP example for Claude, OAuth 2.1 with PKCE | Official page describes a Claude connector flow and 14 capability groups. General third-party application registration, OAuth client credentials/redirect registration, full tool JSON schemas, terms for backend use, SLA/rate limits, and supported non-Claude client behavior are not established in the public page. Integration is not implemented. Continue with CSV and a provider boundary. |
| MCP protocol | Official Python MCP SDK, separate typed server and backend client | Select compatible documented SDK version during MCP milestone. |

### INDmoney verification before connecting (historical decision)

**Update, 7 November 2026:** the user explicitly requested their personal INDmoney connection. The remote OAuth/PKCE client, encrypted credentials, holdings preview/import and portfolio controls are implemented; public metadata and dynamic registration were verified against the real endpoint. The previous implementation deferral below is superseded for this personal flow. Private holdings still require account-owner sign-in. See [current INDmoney implementation and limits](indmoney.md).

1. Ask INDmoney whether the official endpoint permits a custom application/backend client, not only a Claude connector; obtain supported auth/client registration and redirect requirements.
2. Obtain complete `tools/list` schemas, pagination/limits, error behavior, token lifetime/refresh/revocation semantics, and consent scopes.
3. Confirm terms permit the intended storage, processing, and display of portfolio/market data; confirm rate limits and production support.
4. Test a vendor-supported OAuth flow without asking users for INDmoney password, OTP, or MPIN. Never scrape account pages or reverse engineer private endpoints.
5. Only implement after authorization and user-scoped token handling are confirmed. Keep CSV usable regardless.

**Verified public source (accessed 2026-10-29):** [INDmoney MCP](https://www.indmoney.com/mcp). The page describes read-only operation, OAuth 2.1 + PKCE, an endpoint, and a Claude connector setup. These statements are vendor-published; they do not establish a supported custom-backend integration contract.

## Implemented foundation and data API milestones

**Days 1–2: service and repository foundation.** These files establish:

- `README.md` — local start command and scope.
- `.gitignore` — excludes local environments, secrets, and build artifacts.
- `backend/requirements.txt` — initial FastAPI/Uvicorn dependencies.
- `backend/app/main.py` — app construction and route registration.
- `backend/app/api/health.py` — dependency-free liveness endpoint.
- `backend/app/__init__.py`, `backend/app/api/__init__.py` — Python packages.
- `docs/architecture.md` — this architecture, schema, provider/MCP questions, and risks.
- `backend/app/core/config.py` and `backend/app/db/session.py` — typed settings and application database lifecycle.
- `docker-compose.yml` and `.env.example` — local PostgreSQL/pgvector and sample configuration.

**Milestone exit:** API starts locally, `/health` returns `{"status":"ok"}`, and `/docs` exposes the service schema.

**Days 3–5: initial data and access API.** SQLAlchemy models and the first Alembic migration define users, portfolios, instruments, and holdings. Registration and login use Argon2 password hashes and signed, expiring bearer tokens. Portfolio and holdings services derive ownership from the verified user dependency and scope every object lookup by that user. Apply the migration from `backend/` with `alembic upgrade head`.

**Days 6–8: CSV intake and deterministic analytics.** CSV import uses a documented UTF-8 template, enforces file/row limits, reports validation issues by row and field, and persists valid rows. Instrument sector is optional metadata added through migration `0002`. The analytics engine uses Decimal arithmetic for cost basis, supplied-price market value, unrealized P/L, allocations, asset/sector mix, largest position, and a Herfindahl concentration index. Missing, mismatched, stale, and undated prices remain visible and do not create complete aggregate market metrics. The analytics API is user-scoped and accepts optional manually supplied prices. No provider lookup or FX conversion is implemented.

**Current boundary:** Portfolio endpoints accept manual entries and CSV imports. Prices are user-supplied reference inputs; Day 11's source review intentionally selected no provider because public API access did not establish this app's multi-user display, caching, and derived-data rights. External-account connections are not implemented. The provider comparison and selection gate are recorded in [docs/data_sources.md](data_sources.md). The local signing key in `.env.example` is for development only.

**Day 9: frontend foundation.** `frontend/` contains the Vite, React, TypeScript, and Tailwind application shell, client-side routes, a typed API client, and explicit loading, error, and empty states. The overview checks `/health`; the portfolio and research routes are intentionally empty until their later milestones. The backend allows the two local Vite origins by default through `CORS_ORIGINS`; deployments should set that list to their actual frontend origins. Start the UI with `npm install` and `npm run dev` from `frontend/`.

**Day 10: portfolio and dashboard UI.** The frontend now signs users in or registers them against the existing auth API, keeps the bearer token for the browser session, and supports portfolio creation and user-scoped CSV imports. Dashboard and portfolio views read holdings and analytics from the backend, visualize asset and sector cost-basis mix, and show per-position cost basis, optional market figures, and price freshness. Missing prices remain explicit; the UI does not create sample market figures. CSV import results include imported counts and row/field errors. Company research remains an empty state pending an authorized provider and disclosure sources.

**Day 11: provider research and selection.** `docs/data_sources.md` compares official Upstox and Dhan broker APIs with NSE Data & Analytics and BSE data products. It records coverage/identifiers, public prices and request limits where published, account and identifier constraints, exchange terms, disclosure links, and follow-up questions. No provider was selected: public broker API access does not establish this app's onward display and storage rights, while exchange products require a product-specific agreement and budget approval. Manual prices and CSV remain the supported no-provider path. NSE's public MCP is explicitly non-commercial and is not approved for this product.

**Day 12: provider contract and unavailable path.** `backend/app/schemas/financial_data.py` defines typed profile, quote, provenance, and available/unavailable result models. `backend/app/integrations/financial_data/` defines the async read-only provider interface and the default no-provider adapter. The financial data service enforces a configured timeout and maps timeouts/provider failures to stable unavailable states. Authenticated `GET /financial-data/profile/{symbol}` and `/financial-data/price/{symbol}` expose those states. `FINANCIAL_DATA_PROVIDER=none` is the default; unknown providers fail closed and do not trigger network calls. The first vendor-specific adapter remains gated on written access and downstream display/storage terms, as recorded in [docs/data_sources.md](data_sources.md).

## Main technical risks and controls

The milestone descriptions above record the foundation as it was built. Days 13–30 now add persisted provider caches/manual prices, a company research/library UI, PDF extraction/chunking, PostgreSQL full-text and pgvector indexes, bounded hybrid retrieval and extractive answers, official-SDK read-only MCP tools/client, a bounded LangGraph review with saved reports, portfolio-scoped chat and UI, deletion and privacy controls, evaluation and Docker deployment. [Acceptance](acceptance.md) is the current feature/check matrix; [RAG](rag_pipeline.md), [MCP](mcp_design.md), [security](security.md) and [demo setup](demo_guide.md) describe the implemented behavior. The local model baseline is lexical feature hashing, and no generative LLM or licensed vendor is configured. Optional semantic/cross-encoder loading requires operator-provisioned models and further evaluation.

- **Unlicensed, stale, or incomplete financial data:** select providers only after checking official terms and coverage; stamp values with provider, reporting period, currency, and as-of time; mark unavailable/stale data rather than fabricating values.
- **Cross-user portfolio disclosure:** derive user identity from verified auth, enforce ownership in services/queries, and test manipulated object IDs in the API phase.
- **Incorrect return claims:** start with quantity/cost-basis unrealized P&L; label assumptions and exclude time-weighted or money-weighted return claims unless all required cash flows and methodology exist.
- **Poor financial retrieval/citations:** retain page/document metadata, combine exact keyword retrieval with semantic retrieval, rerank, require evidence for document facts, and evaluate citation correctness.
- **Prompt injection in uploaded files:** treat document text as untrusted evidence, isolate it from system instructions, constrain tools, and test adversarial documents.
- **INDmoney deployment scope:** the personal OAuth/holdings flow is now implemented as explicitly requested. Do not represent untested private account access as verified, or assume this establishes commercial redistribution rights. See `docs/indmoney.md`.
- **LLM tool abuse or unbounded workflow:** expose narrow typed read-only tools; enforce authorization outside model inputs; cap retries, time, and context; return partial results with gaps.
- **Scope and dependency sprawl:** implement phase gates, add infrastructure only when its milestone needs it, and keep deterministic logic separate from AI synthesis.
