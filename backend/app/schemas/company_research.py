from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CompanyMatch(BaseModel):
    symbol: str
    exchange: Literal["NSE", "BSE"]
    name: str


class CompanySearch(BaseModel):
    status: Literal["available", "unavailable"]
    matches: list[CompanyMatch] = Field(default_factory=list)
    note: str


class CompanyMetric(BaseModel):
    label: str
    value: str | None
    unit: str
    period: str


class StatementRow(BaseModel):
    label: str
    unit: Literal["currency", "per_share"] = "currency"
    values: list[str | None]


class CompanyStatement(BaseModel):
    title: str
    currency: str
    periods: list[str]
    rows: list[StatementRow]


class CompanySnapshot(BaseModel):
    status: Literal["available", "unavailable"]
    symbol: str
    exchange: str
    provider: str = "Yahoo Finance via yfinance"
    retrieved_at: datetime
    expires_at: datetime | None = None
    cached: bool = False
    source_url: str
    screener_url: str
    name: str | None = None
    sector: str | None = None
    industry: str | None = None
    currency: str | None = None
    price: str | None = None
    price_as_of: datetime | None = None
    metrics: list[CompanyMetric] = Field(default_factory=list)
    statements: list[CompanyStatement] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
