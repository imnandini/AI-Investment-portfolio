# Reproducible evaluation

Run from the repository root using the project Python environment:

```powershell
python -m pytest backend/tests -q
python evaluation/scripts/evaluate.py
cd frontend
npm ci
npm run build
npm test
npm run test:e2e
```

The browser test requires the full app at `http://127.0.0.1:8080`, Chromium (`npx playwright install chromium`), and the synthetic sample PDF. It creates its own disposable account and exercises registration, CSV import, PDF indexing, evidence search, portfolio chat and saved-review reopening. Screenshots are saved under `evaluation/reports/`; failure traces stay in the ignored frontend test-results directory.

`evaluation/datasets/research_questions.jsonl` is a six-case synthetic corpus with expected supporting documents, metadata filters and outside-corpus questions. `evaluation/scripts/evaluate.py` creates an isolated in-memory database, computes Recall@5 and MRR on answerable cases, checks all returned page/excerpt citations against the ingested corpus, verifies abstention on unanswerable cases and measures local retrieval latency. It writes actual environment, dataset hash, per-case results and limitations to `evaluation/reports/latest.json`.

The default baseline makes no external model calls and incurs no provider token cost. Measured latency is retrieval-only; it excludes PDF intake, container startup, network latency and concurrency. This small synthetic evaluation is a regression check, not a financial accuracy benchmark or production SLA. Semantic embeddings and cross-encoder options require a separately provisioned local model and a larger evaluation before quality claims.

Backend tests cover exact Decimal arithmetic, incomplete and foreign-currency prices, source cache expiry/errors, PDF classifications, filters/citations, auth boundaries, prompt-like source content, graph branches, history persistence and deletion. Frontend tests cover cited text rendering, empty/outside-corpus research, saved partial reports and visible chat errors. Real stdio MCP and PostgreSQL checks are documented by the deployment smoke report.
