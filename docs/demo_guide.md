# Repeatable local demo

Requirements: Docker Desktop with Linux containers, or Python 3.13+ / Node 24+ for native development. Copy `.env.example` to `.env` only when no `.env` exists; retain existing secrets. Set a unique local database password and signing key.

From the repository root:

```powershell
docker compose up -d --build
docker compose ps
```

Open `http://127.0.0.1:8080`. API docs are at `http://127.0.0.1:8000/docs`. Backend startup applies Alembic migrations after the database health check. The frontend proxies `/api` to the backend. Native frontend development uses `VITE_API_BASE_URL` from `frontend/.env.local`.

1. Create a disposable account. Create a portfolio named **SYNTHETIC demo portfolio**.
2. Import `sample_data/synthetic_holdings.csv`. AAA is a fictional test symbol; all its values are synthetic.
3. Observe cost basis and missing market metrics. Optionally save a manual reference price with the current local as-of time; it remains a user-entered figure.
4. In Research, upload `sample_data/synthetic_report.pdf` with company `AAA`, kind `annual_report`, period `FY2026`, and a title beginning **SYNTHETIC**. The PDF is clearly labeled and is not a real filing.
5. Search `revenue risk`, inspect page citations, then search `zebra astrophysics` to see insufficient evidence. Company lookup explicitly shows that provider data/trends are unavailable.
6. Open Research chat, select the portfolio and ask `revenue risk`. Inspect portfolio context, activity and source passages.
7. Start a Portfolio review, inspect calculation/source/data-gap findings, and reload to reopen its saved report. Without live feeds, results remain partial with explicit limitations.
8. Delete the document to remove its chunks and saved research history. For full cleanup, use authenticated `DELETE /auth/me` for this disposable account.

No demo account, synthetic prices or holdings are silently inserted. Regenerate the supplied PDF with `python sample_data/create_demo_pdf.py` after installing backend requirements.

Troubleshooting:

- Docker pipe errors: start Docker Desktop and wait for the Linux engine. Check `docker compose ps` and `docker compose logs --tail 80 backend`.
- Unhealthy backend: ensure the database password matches the existing volume. Changing an environment variable does not reset an existing PostgreSQL password. Preserve the volume; correct the configuration or perform an intentional database credential change.
- Port conflict: stop the conflicting local process or change the published port and frontend API configuration.
- Database permission error creating `vector`: apply the extension once with an authorized database administrator. Do not grant superuser privileges to a public application.
- 401: sign in again; tokens expire. 429: wait one minute. 413: reduce file size.
- PDF `scanned_or_empty`: provide a text PDF; OCR is not implemented. Index error: check optional model configuration, delete the failed record and upload again.
- Missing financial data is the expected no-provider state. This app does not fetch exchange websites or broker accounts.

Use `docker compose stop` to stop services while preserving data. This guide does not instruct removing database volumes.
