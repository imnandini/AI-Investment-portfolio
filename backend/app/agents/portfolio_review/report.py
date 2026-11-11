from typing import Literal
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, model_validator
from app.schemas.research import Evidence


class Finding(BaseModel):
    title: str
    text: str
    basis: Literal["calculation", "source_excerpt", "headline_signal", "data_gap"]
    evidence_indices: list[int] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)


class NewsSource(BaseModel):
    id: str
    title: str
    url: str
    publisher: str
    published_at: datetime


class CompanyNews(BaseModel):
    status: Literal["available", "empty", "unavailable", "not_checked"]
    checked_at: datetime | None = None
    provider: str | None = None
    cached: bool = False
    note: str
    articles: list[NewsSource] = Field(default_factory=list)


class NewsSignal(BaseModel):
    title: str
    text: str
    explanation: str
    source_ids: list[str]


class CompanyReview(BaseModel):
    name: str
    symbol: str
    exchange: str
    is_fund: bool
    weight_pct: Decimal | None = None
    weight_basis: str
    unrealized_return_pct: Decimal | None = None
    price_as_of: datetime | None = None
    view: str
    portfolio_impact: str
    positive_signals: list[NewsSignal] = Field(default_factory=list)
    concern_signals: list[NewsSignal] = Field(default_factory=list)
    news: CompanyNews


class ReviewCoverage(BaseModel):
    total_positions: int
    eligible_positions: int
    selected_positions: int
    checked_positions: int
    positions_with_news: int
    positions_without_news: int
    unreviewed_positions: int
    excluded_positions: int
    checked_weight_pct: Decimal | None = None
    weight_basis: str
    article_count: int
    selection_policy: str


class ReviewReport(BaseModel):
    methodology_version: str = "portfolio-review-v2"
    assessment_status: Literal["complete", "partial"] = "partial"
    generated_at: datetime | None = None
    summary: str
    analytics: dict
    findings: list[Finding]
    evidence: list[Evidence]
    limitations: list[str]
    follow_up_questions: list[str]
    activities: list[str]
    company_reviews: list[CompanyReview] = Field(default_factory=list)
    coverage: ReviewCoverage | None = None

    @model_validator(mode="after")
    def citations_valid(self):
        sources = {source.id for company in self.company_reviews for source in company.news.articles}
        for finding in self.findings:
            if any(i < 0 or i >= len(self.evidence) for i in finding.evidence_indices):
                raise ValueError("Finding references missing evidence.")
            if finding.basis == "source_excerpt" and not finding.evidence_indices:
                raise ValueError("Source findings require citations.")
            if any(source_id not in sources for source_id in finding.source_ids):
                raise ValueError("Finding references missing news sources.")
            if finding.basis == "headline_signal" and not finding.source_ids:
                raise ValueError("Headline findings require news sources.")
        for company in self.company_reviews:
            own_sources = {article.id for article in company.news.articles}
            for signal in company.positive_signals + company.concern_signals:
                if not signal.source_ids or any(identifier not in own_sources for identifier in signal.source_ids):
                    raise ValueError("Company signals require matching news sources.")
        return self
