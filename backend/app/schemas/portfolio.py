from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator


CurrencyCode = Annotated[str, StringConstraints(pattern=r"^[A-Za-z]{3}$", min_length=3, max_length=3)]
Symbol = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)]


class PortfolioCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    base_currency: CurrencyCode = "INR"

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be blank.")
        return value

    @field_validator("base_currency")
    @classmethod
    def uppercase_currency(cls, value: str) -> str:
        return value.upper()


class PortfolioUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    base_currency: CurrencyCode | None = None

    @field_validator("name")
    @classmethod
    def trim_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be blank.")
        return value

    @field_validator("base_currency")
    @classmethod
    def uppercase_optional_currency(cls, value: str | None) -> str | None:
        return value.upper() if value is not None else None


class InstrumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    canonical_symbol: str
    exchange: str
    asset_type: str
    currency: str
    sector: str | None


class HoldingCreate(BaseModel):
    symbol: Symbol
    exchange: str | None = Field(default=None, max_length=32)
    asset_type: str = Field(default="equity", min_length=1, max_length=32)
    currency: CurrencyCode = "INR"
    sector: str | None = Field(default=None, max_length=80)
    quantity: Decimal = Field(gt=0, max_digits=24, decimal_places=10)
    average_cost: Decimal = Field(ge=0, max_digits=24, decimal_places=10)
    purchase_date: date | None = None

    @field_validator("symbol")
    @classmethod
    def uppercase_symbol(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("exchange", "asset_type")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip().upper()
        if not value:
            raise ValueError("Value cannot be blank.")
        return value

    @field_validator("sector")
    @classmethod
    def normalize_sector(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Sector cannot be blank.")
        return value

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, value: str) -> str:
        return value.upper()


class HoldingUpdate(BaseModel):
    quantity: Decimal | None = Field(default=None, gt=0, max_digits=24, decimal_places=10)
    average_cost: Decimal | None = Field(default=None, ge=0, max_digits=24, decimal_places=10)
    purchase_date: date | None = None

    @field_validator("quantity", "average_cost")
    @classmethod
    def reject_null_numeric_values(cls, value: Decimal | None) -> Decimal:
        if value is None:
            raise ValueError("Value cannot be null.")
        return value

    @model_validator(mode="after")
    def require_an_update(self) -> "HoldingUpdate":
        if not self.model_fields_set:
            raise ValueError("Provide at least one holding field to update.")
        return self


class HoldingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    quantity: Decimal
    average_cost: Decimal
    purchase_date: date | None
    instrument: InstrumentRead


class PortfolioRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    base_currency: str
    created_at: datetime
    updated_at: datetime


class PortfolioDetail(PortfolioRead):
    holdings: list[HoldingRead]
