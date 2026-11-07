# Architecture and interview discussion

Start with the demo in [demo_guide.md](demo_guide.md). Explain the ownership boundary first: the verified user selects a portfolio; deterministic Decimal calculations produce structure and completeness metadata; user-supplied documents provide quoted evidence. The review graph combines those two without making investment recommendations or executing trades.

Key design decisions:

- **Precise calculations outside AI:** quantity/cost/price arithmetic and currency/freshness rules live in a separately tested engine. An LLM should never invent or silently recompute authoritative totals.
- **Provenance before coverage:** company lookup returns timestamped cache/provider states. No licensed feed is enabled, so the UI exposes missing figures rather than sample values. Broker API access and data display/storage rights are separate questions.
- **Private document retrieval:** user ownership is part of every query; page boundaries and metadata survive ingestion. PostgreSQL full text plus pgvector candidates use reciprocal-rank fusion. The offline hash baseline is lexical; optional local semantic and cross-encoder models need separate provisioning and evaluation.
- **Extractive grounding:** quoting source passages provides a working no-key path and makes citation checks deterministic. It cannot synthesize an investment thesis or reconcile complex financial statements. A future generative adapter would need schema validation, citation entailment checks, bounded context, refusal behavior and evaluated costs.
- **Bounded orchestration:** LangGraph has explicit calculation, research/empty, verification and report nodes, at most five research targets and a recursion limit. Results persist with methodology and data gaps. The present request is synchronous and progress UI shows an in-flight stage; resumable jobs and streamed per-node progress would be a later scaling step.
- **MCP as an integration boundary:** a separate official-SDK stdio server offers four typed read-only tools. Authentication stays in the API, with a per-client bearer token passed through process environment. Internal graph/chat calls reuse the same services directly to avoid unnecessary IPC. INDmoney is intentionally gated pending its supported custom-client contract.
- **Privacy and local operations:** logs omit source text and credentials. Data deletion removes derived saved excerpts. Docker health checks and migration-before-start provide a repeatable local setup; this is not a public production security certification.

Trade-offs to discuss: HNSW approximate search versus exact vector scans, character chunking versus layout-aware financial-table extraction, local embeddings versus hosted models, in-process rate limits versus a shared gateway, synchronous review requests versus a durable task queue, and user-uploaded filings versus licensed source ingestion. Each should be evaluated against actual corpus size, access terms and measured workload.

Use [acceptance.md](acceptance.md) to distinguish shipped functionality, measured checks and external/model provisioning gates. Do not present synthetic retrieval scores as real-world research quality or claim access to unconnected brokerage data.
