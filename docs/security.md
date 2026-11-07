# Security and privacy

Authentication uses Argon2 and expiring HS256 tokens with issuer verification. All portfolio, price, document, review, chat and MCP endpoints derive the user from the verified bearer token. No request body may select an owner. Cross-user object IDs return 404. Source cache records hold only provider lookup results; uploaded company documents remain user-scoped.

Browser tokens are held in sessionStorage and cleared on sign-out. HTTPS, a strong secret of at least 32 characters and explicit CORS origins are required for production. Docker binds published services to loopback for local use. The supplied Compose settings are a local deployment, not a hardened public service. API response bodies are marked no-store; Nginx applies a restrictive content security policy. No HTML from uploaded content is rendered.

The middleware limits request bodies to 6 MB, including bodies without Content-Length, and bounds each upload read to 15 seconds. PDF validation further limits bytes, pages and extracted text; CSV limits remain 1 MB / 500 rows. Per-process per-IP request limits default to 120/minute; forwarded headers are not trusted. A shared gateway/rate-limit store and worker-isolated PDF parsing are recommended before hostile public traffic. PDF page/text limits are not a complete defense against pathological compressed content. OCR is unavailable. No arbitrary URLs are fetched.

Document text is untrusted evidence, quoted by an extractive answerer. It cannot issue instructions or choose tools. Local optional model loading disables remote code and automatic downloads. No paid LLM provider is configured. LangSmith tracing is disabled in Compose; keep external tracing disabled for private data. Request logs contain only request ID, method, route template, status and duration, with no bodies, query strings, tokens, emails or source passages. Run Uvicorn with `--no-access-log` to avoid its separate raw-URL log.

Deletion endpoints:

- `DELETE /documents/{id}` deletes the owned document/chunks and all of the owner's chat/reviews, including saved excerpts.
- `DELETE /portfolios/{id}/chat` clears that portfolio's chat.
- `DELETE /portfolios/{id}/reviews/{id}` deletes one saved report.
- `DELETE /portfolios/{id}` cascades holdings, manual prices, chat and reviews.
- `DELETE /auth/me` permanently removes the account and all its owned data; old tokens then fail because the user is gone.

Shared instrument identifiers and public/provider cache entries are not account-owned and remain. Original PDFs are not stored. Database backups, Docker volumes and browser copies are outside application deletion and need operator retention policies. Do not publish `.env`, copy real user data into tests, or expose the database port to the internet.

Automated checks cover auth and owner boundaries, malicious URL metadata, prompt-like PDF text, upload constraints, missing/stale/future prices, log privacy, request limits, document/account deletion and the MCP allowlist. The test results and remaining limits are recorded in [acceptance.md](acceptance.md).
