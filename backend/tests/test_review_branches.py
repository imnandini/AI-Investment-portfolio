from app.agents.portfolio_review.verification import evidence_gaps
from app.agents.portfolio_review.report import ReviewReport
from app.schemas.research import Evidence
from pydantic import ValidationError
from uuid import uuid4
import pytest


def test_review_without_holdings_routes_to_partial_report(api_context):
    client, _, portfolio, headers, _ = api_context
    response = client.post(f"/portfolios/{portfolio.id}/reviews", headers=headers)
    assert response.status_code == 201
    report = response.json()["report"]
    assert "Skipped research: no holdings" in report["activities"]
    assert any("no holdings" in note for note in report["limitations"])
    saved = client.get(f"/portfolios/{portfolio.id}/reviews/{response.json()['id']}", headers=headers).json()
    assert saved["report"] == report


def test_numeric_ambiguity_preserves_periods_and_never_selects_value():
    excerpts = [dict(company="AAA", period="FY2026", text="Revenue was 120 units."), dict(company="AAA", period="FY2026", text="Revenue was 140 units.")]
    assert "no value was chosen" in evidence_gaps(excerpts)[0]
    excerpts[1]["period"] = "FY2025"
    assert evidence_gaps(excerpts) == []


def test_report_rejects_broken_citations():
    with pytest.raises(ValidationError):
        ReviewReport(summary="test", analytics={}, findings=[dict(title="Fact", text="Invented", basis="source_excerpt", evidence_indices=[0])], evidence=[], limitations=[], follow_up_questions=[], activities=[])
