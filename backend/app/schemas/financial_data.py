from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator


Symbol = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)]
Exchange = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)]
Currency = Annotated[str, StringConstraints(pattern=r"^[A-Za-z]{3}$", min_length=3, max_length=3)]

UnavailableCode = Literal[
    "provider_not_configured",
    "provider_not_implemented",
    "not_found",
    "rate_limited",
    "timeout",
    "authentication_failed",
    "invalid_response",
    "provider_error",
]


class SourceMetadata(BaseModel):
    provider: str = Field(min_length=1, max_length=80)
    source_identifier: str | None = Field(default=None, max_length=160)
    retrieved_at: datetime
    as_of: datetime | None = None

    @field_validator("retrieved_at", "as_of")
    @classmethod
    def normalize_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.utcoffset() is None:
            raise ValueError("Source timestamps must include a timezone.")
        return value.astimezone(timezone.utc)


class CompanyProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: Symbol
    exchange: Exchange
    company_name: str = Field(min_length=1, max_length=200)
    isin: str | None = Field(default=None, max_length=12)
    asset_type: str | None = Field(default=None, max_length=32)
    currency: Currency | None = None
    sector: str | None = Field(default=None, max_length=120)
    industry: str | None = Field(default=None, max_length=160)
    website: str | None = Field(default=None, max_length=500)

    @field_validator("symbol", "exchange")
    @classmethod
    def normalize_identifier(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        return value.upper() if value is not None else None


class PriceQuote(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: Symbol
    exchange: Exchange
    price: Decimal = Field(gt=0, max_digits=24, decimal_places=10)
    currency: Currency
    as_of: datetime | None = None

    @field_validator("symbol", "exchange")
    @classmethod
    def normalize_identifier(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()

    @field_validator("as_of")
    @classmethod
    def normalize_as_of(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.utcoffset() is None:
            raise ValueError("Price as_of must include a timezone.")
        return value.astimezone(timezone.utc)


class ProviderIssue(BaseModel):
    code: UnavailableCode
    message: str = Field(min_length=1, max_length=240)
    retryable: bool = False


T = TypeVar("T")


class ProviderResult(BaseModel, Generic[T]):
    model_config = ConfigDict(extra="forbid")

    status: Literal["available", "unavailable"]
    data: T | None = None
    source: SourceMetadata | None = None
    issue: ProviderIssue | None = None

    @model_validator(mode="after")
    def validate_result_state(self) -> "ProviderResult[T]":
        if self.status == "available" and (self.data is None or self.source is None or self.issue is not None):
            raise ValueError("Available results require data and source metadata, with no issue.")
        if self.status == "unavailable" and (
            self.data is not None or self.source is not None or self.issue is None
        ):
            raise ValueError("Unavailable results require an issue and cannot contain data or source metadata.")
        return self
