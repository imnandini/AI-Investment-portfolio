from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class PriceComparison(BaseModel):
    label: str
    from_date: date
    to_date: date
    previous_value: Decimal
    latest_value: Decimal
    change: Decimal
    change_pct: Decimal | None


class DailyPriceOverview(BaseModel):
    configured: bool
    provider: str = "Daily closing prices"
    requested_through: date
    latest_date: date | None = None
    checked_at: datetime | None = None
    covered_positions: int = 0
    position_count: int = 0
    notes: list[str] = []
    comparisons: list[PriceComparison] = []
    comparison_basis: str = "Current quantities revalued at provider closes; excludes trades, dividends and fees. Provider split adjustments may affect history. These are price comparisons, not total investment returns."
