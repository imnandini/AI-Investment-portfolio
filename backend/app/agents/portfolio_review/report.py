from typing import Literal
from pydantic import BaseModel, Field, model_validator
from app.schemas.research import Evidence


class Finding(BaseModel):
    title: str
    text: str
    basis: Literal["calculation", "source_excerpt", "data_gap"]
    evidence_indices: list[int] = Field(default_factory=list)


class ReviewReport(BaseModel):
    methodology_version: str = "portfolio-review-v1"
    summary: str
    analytics: dict
    findings: list[Finding]
    evidence: list[Evidence]
    limitations: list[str]
    follow_up_questions: list[str]
    activities: list[str]

    @model_validator(mode="after")
    def citations_valid(self):
        for finding in self.findings:
            if any(i < 0 or i >= len(self.evidence) for i in finding.evidence_indices):
                raise ValueError("Finding references missing evidence.")
            if finding.basis == "source_excerpt" and not finding.evidence_indices:
                raise ValueError("Source findings require citations.")
        return self
