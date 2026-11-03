from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator


Currency = Annotated[str, StringConstraints(pattern=r"^[A-Za-z]{3}$", min_length=3, max_length=3)]


class PriceInput(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    exchange: str = Field(default="UNKNOWN", min_length=1, max_length=32)
    price: Decimal = Field(gt=0, max_digits=24, decimal_places=10)
    currency: Currency
    as_of: datetime | None = None

    @field_validator("symbol", "exchange")
    @classmethod
    def normalize_identifier(cls, value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise ValueError("Value cannot be blank.")
        return value

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()

    @field_validator("as_of")
    @classmethod
    def require_aware_as_of(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("as_of must include a timezone.")
        return value.astimezone(timezone.utc) if value is not None else None


class HoldingAnalytics(BaseModel):
    symbol: str
    exchange: str
    asset_type: str
    sector: str | None
    currency: str
    quantity: Decimal
    average_cost: Decimal
    cost_basis: Decimal
    current_price: Decimal | None
    market_value: Decimal | None
    unrealized_pl: Decimal | None
    market_allocation_pct: Decimal | None
    cost_basis_allocation_pct: Decimal | None
    price_as_of: datetime | None
    price_status: Literal["available", "missing", "currency_mismatch", "stale", "unknown_freshness"]


class MixEntry(BaseModel):
    name: str
    cost_basis: Decimal
    allocation_pct: Decimal | None


class PortfolioAnalytics(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    portfolio_id: str
    base_currency: str
    methodology: str
    cost_basis_total: Decimal | None
    market_value_total: Decimal | None
    unrealized_pl_total: Decimal | None
    largest_holding_symbol: str | None
    largest_holding_allocation_pct: Decimal | None
    concentration_index: Decimal | None
    asset_mix: list[MixEntry]
    sector_mix: list[MixEntry]
    positions: list[HoldingAnalytics]
    priced_position_count: int
    unpriced_position_count: int
    complete: bool
    completeness_notes: list[str]
