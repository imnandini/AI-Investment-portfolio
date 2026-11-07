from datetime import date, datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


class DocumentMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=200)
    company: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9._-]+$")
    kind: Literal["annual_report", "quarterly_results", "disclosure", "research", "other"] = "other"
    period: str | None = Field(default=None, max_length=40)
    publication_date: date | None = None
    source_url: HttpUrl | None = None

    @field_validator("company")
    @classmethod
    def normalize_company(cls, value):
        return value.upper()


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    title: str
    company: str
    kind: str
    period: str | None
    publication_date: date | None
    source_url: str | None
    page_count: int
    status: str
    error: str | None
    created_at: datetime


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    query: str = Field(min_length=2, max_length=1000)
    company: str | None = Field(default=None, max_length=32)
    companies: list[str] | None = Field(default=None, max_length=50)
    kind: str | None = Field(default=None, max_length=40)
    period: str | None = Field(default=None, max_length=40)
    published_after: date | None = None
    published_before: date | None = None
    page: int | None = Field(default=None, ge=1, le=100)
    limit: int = Field(default=5, ge=1, le=10)

    @model_validator(mode="after")
    def dates_ordered(self):
        if self.published_after and self.published_before and self.published_after > self.published_before:
            raise ValueError("Published-after must precede published-before.")
        return self


class Evidence(BaseModel):
    chunk_id: UUID
    document_id: UUID
    title: str
    company: str
    page: int
    period: str | None
    publication_date: date | None
    source_url: str | None
    text: str
    score: float


class Answer(BaseModel):
    status: Literal["supported", "insufficient_evidence"]
    answer: str
    evidence: list[Evidence]
    limitations: list[str]
    activities: list[str]
    method: str = "extractive-v1"
