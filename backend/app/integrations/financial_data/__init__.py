"""Typed financial data provider contracts and configured adapters."""

from app.integrations.financial_data.base import FinancialDataProvider, ProviderError
from app.integrations.financial_data.unavailable import UnavailableFinancialDataProvider

__all__ = ["FinancialDataProvider", "ProviderError", "UnavailableFinancialDataProvider"]
