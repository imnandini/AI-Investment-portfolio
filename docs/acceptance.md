# Roadmap implementation and acceptance

Reviewed 7 November 2026. The local no-provider application implements the remaining roadmap workflows. **This is not unconditional completion of every external/model-dependent exit check.** Day 12's licensed adapter and Day 17's provisioned semantic model remain gated. The existing source-access decision is preserved. No brokerage or market-data access was invented.

| Day | Delivered behavior / evidence | State |
|---|---|---|
| 1 | Architecture, risks, health API, documented ownership | Complete |
| 2 | Typed settings; PostgreSQL/pgvector Compose health checks; database lifecycle | Complete |
| 3 | User/portfolio/instrument/holding migrations; isolated migration checks | Complete |
| 4 | Registration/login, Argon2, signed expiring tokens, owner checks | Complete |
| 5 | Protected portfolio and holding CRUD | Complete |
| 6 | Bounded UTF-8 CSV import with row-level errors and duplicate checks | Complete |
| 7 | Decimal cost/market/allocation/concentration calculations; explicit missing/stale/currency behavior | Complete |
| 8 | Analytics API, hand-worked examples and access tests; fixed stale ORM holding reads | Complete |
| 9 | React/TypeScript/Vite app, routes, typed client and visible error/loading states | Complete |
| 10 | Portfolio/dashboard UI, imports, allocations and saved manual price entry | Complete |
| 11 | Provider decision record and supported manual/CSV path; no unauthorized feed | Complete |
| 12 | Typed provider/no-provider boundary, controlled failures/timeouts; **licensed vendor adapter requires approved access terms** | Gated |
| 13 | Persistent lookup/source payloads, retrieval/expiry times, source freshness and error states | Complete for configured providers |
| 14 | Company lookup and private research library with explicit missing metrics/trends | Complete for no-provider path |
| 15 | PDF byte/type/size/page/text limits, hash, duplicate checks, processing/error classifications | Complete |
| 16 | Page-preserving chunks with overlap and company/kind/period/date/source metadata | Complete |
| 17 | pgvector/HNSW and PostgreSQL GIN indexes; offline lexical vectors; configurable local semantic model and reindex API; **semantic weights/dependencies not provisioned or evaluated** | Gated |
| 18 | Owner/metadata filters, keyword/vector candidates, RRF, bounded search results | Complete; default vectors are lexical |
| 19 | Optional local cross-encoder, extractive cited answers, abstention, reproducible retrieval/citation dataset | Complete for extractive baseline; optional reranker unmeasured |
| 20 | Separate official-SDK stdio server; four typed, read-only tools backed by real APIs | Complete |
| 21 | Bounded backend SDK client, discovery/invocation, token-bound ownership; INDmoney remains disabled | Complete for local MCP |
| 22 | Typed LangGraph state, authorized calculations and at most five research targets | Complete |
| 23 | Research/empty routing, retrieval-failure gaps, conservative numeric ambiguity checks, partial reports | Complete for configured sources |
| 24 | Schema-validated findings/citations, methodology, saved reports and protected history APIs | Complete |
| 25 | Portfolio-aware extractive chat, visible activity/evidence, private history and outside-corpus response | Complete for extractive baseline |
| 26 | Review launch/in-flight/result/history UI, limitations, citations and reopening | Complete; synchronous request |
| 27 | Auth/ownership checks, bounded intake, rate limits, safe logs, no-store responses and deletion | Complete for local prototype; see security limits |
| 28 | Backend/frontend tests, live browser test, synthetic retrieval evaluation and real API/MCP smoke report | Complete within documented evaluation scope |
| 29 | Database/API/Nginx frontend Compose; non-root backend; migrations/health checks; labeled synthetic demo | Complete |
| 30 | This acceptance matrix, architecture updates, demo screenshots and interview/trade-off guide | Complete |

Verification artifacts:

Verified results: **29 backend tests, 4 frontend behavior tests, 1 full browser workflow, 6 synthetic retrieval cases, all 4 real MCP tools, and isolated PostgreSQL upgrade/downgrade/re-upgrade/schema checks passed**. The frontend production build passed and npm audit reported zero vulnerabilities in the installed dependency tree. These checks do not constitute a backend dependency audit or production security certification.

- `evaluation/reports/latest.json`: six synthetic retrieval cases, measured Recall@5/MRR, citation/abstention checks, environment and latency limitations.
- `evaluation/reports/deployment_smoke.json`: real PostgreSQL PDF/vector retrieval, manual prices, saved graph reports, four actual stdio MCP tools, denied object lookup, backend MCP route and disposable account deletion.
- `evaluation/reports/research-desktop.png`, `review-desktop.png`, `review-mobile.png`: browser evidence of shipped UI; synthetic figures only.
- `backend/tests/`: calculation, API, PDF/RAG, provider cache/failures, workflow, security/deletion and MCP contract checks.
- `frontend/src/pages/Research.test.tsx`: UI behavior checks. `frontend/e2e/copilot.spec.ts`: complete browser workflow against Docker.
- `backend/tools/check_migrations.py`: upgrade, downgrade to the foundation, re-upgrade and model/schema comparison in a fresh temporary schema. It does not downgrade application tables.

Remaining conditions are specific: obtain a licensed provider agreement before adding a vendor adapter; provision and evaluate a trusted local semantic/reranking model to enable those optional paths; select/evaluate a generative provider if synthesis beyond quoted passages is wanted; obtain INDmoney's supported custom-client terms before connecting it. None of these is silently substituted with fake data. OCR, automatic filing downloads, FX conversion, real-time broker sync, trade execution, durable review jobs and production hardening are not included.

The original planning workbook remains a historical plan. The acceptance matrix and measured reports describe the actual implementation, including gates.
