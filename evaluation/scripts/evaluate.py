"""Repeatable local retrieval evaluation. All figures in the corpus are synthetic."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import statistics
import sys
import time
from uuid import uuid4
from datetime import datetime, timezone
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.db.base import Base
import app.models
from app.models.user import User
from app.models.document import Document
from app.rag.indexing import index_pages
from app.rag.retrieval import retrieve
from app.rag.answering import grounded_answer
from app.schemas.research import SearchRequest
from app.core.config import Settings


def main():
    path = ROOT / "evaluation/datasets/research_questions.jsonl"
    content = path.read_bytes()
    rows = [json.loads(line) for line in content.decode().splitlines() if line.strip()]
    settings = Settings(embedding_provider="hash", reranker_model_path="")
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    cases, recalls, reciprocal, latencies = [], [], [], []
    with Session(engine) as session:
        user = User(email="synthetic-evaluation@example.com", password_hash="unused")
        session.add(user); session.flush()
        keys, texts = {}, {}
        for entry in rows[0]["documents"]:
            doc = Document(user_id=user.id, title=entry["key"], company=entry["company"], kind="annual_report", period=entry["period"], content_hash=hashlib.sha256(entry["text"].encode()).hexdigest(), status="ready", page_count=1)
            session.add(doc); session.flush()
            index_pages(session, doc, [(1, entry["text"])], settings)
            keys[str(doc.id)], texts[str(doc.id)] = entry["key"], entry["text"]
        session.commit()
        for row in rows:
            start = time.perf_counter()
            evidence = retrieve(session, user.id, SearchRequest(query=row["query"], company=row.get("company"), period=row.get("period"), limit=5), settings)
            answer = grounded_answer(evidence)
            elapsed = (time.perf_counter()-start)*1000
            retrieved = [keys[str(item.document_id)] for item in evidence]
            expected = set(row["expected"])
            if expected:
                recalls.append(len(expected & set(retrieved)) / len(expected))
                reciprocal.append(next((1/(i+1) for i,key in enumerate(retrieved) if key in expected), 0))
            correct_citations = all(item.page == 1 and item.text in texts[str(item.document_id)] for item in evidence)
            correct_abstention = bool(expected) or answer.status == "insufficient_evidence"
            cases.append({"id": row["id"], "retrieved": retrieved, "expected": row["expected"], "citation_check": correct_citations, "abstention_check": correct_abstention, "latency_ms": round(elapsed, 3)})
            latencies.append(elapsed)
    result = {"measured_at": datetime.now(timezone.utc).isoformat(), "dataset_sha256": hashlib.sha256(content).hexdigest(), "dataset_version": "synthetic-v1", "environment": {"python": platform.python_version(), "platform": platform.platform(), "sqlalchemy": importlib.metadata.version("sqlalchemy")}, "method": "hash-lexical-v1-384 + keyword + RRF, SQLite reference path", "cases": cases, "metrics": {"recall_at_5": statistics.mean(recalls), "mrr": statistics.mean(reciprocal), "citation_checks_passed": sum(c["citation_check"] for c in cases), "abstention_checks_passed": sum(c["abstention_check"] for c in cases), "case_count": len(cases), "median_latency_ms": round(statistics.median(latencies), 3), "max_latency_ms": round(max(latencies), 3), "external_model_calls": 0, "external_model_cost": 0}, "limitations": ["Small synthetic corpus; not a measure of real financial research quality.", "No semantic model or cross-encoder evaluated.", "Latency excludes PDF extraction and does not establish a production SLA."]}
    out = ROOT / "evaluation/reports/latest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result["metrics"], indent=2))
    if result["metrics"]["recall_at_5"] < 1 or result["metrics"]["mrr"] < 1 or not all(c["citation_check"] and c["abstention_check"] for c in cases):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
