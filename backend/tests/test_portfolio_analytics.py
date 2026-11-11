from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.analytics.models import PriceInput
from app.analytics.portfolio import calculate_portfolio_analytics


def test_complete_inr_prices_reconcile_and_mix_by_cost_basis():
    holdings = [
        SimpleNamespace(
            quantity=Decimal("2"), average_cost=Decimal("100"),
            instrument=SimpleNamespace(canonical_symbol="AAA", exchange="NSE", asset_type="EQUITY", currency="INR", sector="Technology"),
        ),
        SimpleNamespace(
            quantity=Decimal("1"), average_cost=Decimal("200"),
            instrument=SimpleNamespace(canonical_symbol="BBB", exchange="NSE", asset_type="ETF", currency="INR", sector=None),
        ),
    ]
    portfolio = SimpleNamespace(id=uuid4(), base_currency="INR", holdings=holdings)
    result = calculate_portfolio_analytics(portfolio, [
        PriceInput(symbol="aaa", exchange="nse", price=Decimal("125"), currency="INR", as_of=datetime.now(timezone.utc)),
        PriceInput(symbol="BBB", exchange="NSE", price=Decimal("180"), currency="INR", as_of=datetime.now(timezone.utc)),
    ])

    assert result.cost_basis_total == Decimal("400.00")
    assert result.market_value_total == Decimal("430.00")
    assert result.unrealized_pl_total == Decimal("30.00")
    assert result.unrealized_return_pct == Decimal("7.50")
    assert result.positions[0].unrealized_return_pct == Decimal("25.00")
    assert result.positions[1].unrealized_return_pct == Decimal("-10.00")
    assert result.largest_holding_symbol == "AAA"
    assert result.largest_holding_allocation_pct == Decimal("58.14")
    assert result.concentration_index == Decimal("5132.50")
    assert result.complete is True
    assert result.positions[0].market_allocation_pct == Decimal("58.14")
    assert sum(item.allocation_pct for item in result.asset_mix) == Decimal("100.00")
    assert {item.name for item in result.sector_mix} == {"Technology", "Unknown"}


def test_missing_and_mismatched_prices_remain_explicit():
    holding = SimpleNamespace(
        quantity=Decimal("3"), average_cost=Decimal("10"),
        instrument=SimpleNamespace(canonical_symbol="AAA", exchange="NSE", asset_type="EQUITY", currency="INR", sector=None),
    )
    portfolio = SimpleNamespace(id=uuid4(), base_currency="INR", holdings=[holding])
    missing = calculate_portfolio_analytics(portfolio)
    assert missing.cost_basis_total == Decimal("30.00")
    assert missing.market_value_total is None
    assert missing.positions[0].price_status == "missing"
    assert missing.positions[0].unrealized_pl is None
    assert missing.positions[0].unrealized_return_pct is None
    assert missing.largest_holding_symbol is None
    assert missing.concentration_index is None

    mismatch = calculate_portfolio_analytics(portfolio, [
        PriceInput(symbol="AAA", exchange="NSE", price=Decimal("12"), currency="USD"),
    ])
    assert mismatch.positions[0].price_status == "currency_mismatch"
    assert mismatch.positions[0].market_value is None
    assert mismatch.positions[0].unrealized_return_pct is None
    assert any("currency" in note.lower() for note in mismatch.completeness_notes)


def test_stale_and_unknown_freshness_do_not_produce_complete_market_metrics():
    holding = SimpleNamespace(
        quantity=Decimal("3"), average_cost=Decimal("10"),
        instrument=SimpleNamespace(canonical_symbol="AAA", exchange="NSE", asset_type="EQUITY", currency="INR", sector=None),
    )
    portfolio = SimpleNamespace(id=uuid4(), base_currency="INR", holdings=[holding])
    stale = calculate_portfolio_analytics(portfolio, [
        PriceInput(symbol="AAA", exchange="NSE", price=Decimal("12"), currency="INR", as_of=datetime(2020, 1, 1, tzinfo=timezone.utc)),
    ])
    assert stale.positions[0].price_status == "stale"
    assert stale.positions[0].market_value == Decimal("36.00")
    assert stale.market_value_total is None
    assert stale.complete is False
    assert stale.positions[0].unrealized_return_pct is None
    assert stale.unrealized_return_pct is None

    unknown = calculate_portfolio_analytics(portfolio, [
        PriceInput(symbol="AAA", exchange="NSE", price=Decimal("12"), currency="INR"),
    ])
    assert unknown.positions[0].price_status == "unknown_freshness"
    assert unknown.market_value_total is None
    assert unknown.positions[0].unrealized_return_pct is None


def test_duplicate_price_inputs_are_rejected():
    portfolio = SimpleNamespace(id=uuid4(), base_currency="INR", holdings=[])
    price = PriceInput(symbol="AAA", exchange="NSE", price=Decimal("12"), currency="INR")
    with pytest.raises(ValueError, match="Duplicate price"):
        calculate_portfolio_analytics(portfolio, [price, price])


def test_single_position_is_fully_concentrated_and_zero_quantity_is_rejected():
    holding = SimpleNamespace(
        quantity=Decimal("1"), average_cost=Decimal("50"),
        instrument=SimpleNamespace(canonical_symbol="AAA", exchange="NSE", asset_type="EQUITY", currency="INR", sector="Energy"),
    )
    portfolio = SimpleNamespace(id=uuid4(), base_currency="INR", holdings=[holding])
    result = calculate_portfolio_analytics(portfolio, [
        PriceInput(symbol="AAA", exchange="NSE", price=Decimal("50"), currency="INR", as_of=datetime.now(timezone.utc)),
    ])
    assert result.largest_holding_allocation_pct == Decimal("100.00")
    assert result.concentration_index == Decimal("10000.00")
    assert result.positions[0].unrealized_return_pct == Decimal("0.00")

    holding.quantity = Decimal("0")
    with pytest.raises(ValueError, match="positive quantity"):
        calculate_portfolio_analytics(portfolio)


def test_foreign_currency_positions_are_not_added_without_fx():
    holding = SimpleNamespace(
        quantity=Decimal("2"), average_cost=Decimal("10"),
        instrument=SimpleNamespace(canonical_symbol="ABC", exchange="NYSE", asset_type="EQUITY", currency="USD", sector="Technology"),
    )
    portfolio = SimpleNamespace(id=uuid4(), base_currency="INR", holdings=[holding])
    result = calculate_portfolio_analytics(portfolio, [
        PriceInput(symbol="ABC", exchange="NYSE", price=Decimal("12"), currency="USD", as_of=datetime.now(timezone.utc)),
    ])
    assert result.positions[0].market_value == Decimal("24.00")
    assert result.positions[0].unrealized_return_pct == Decimal("20.00")
    assert result.unrealized_return_pct is None
    assert result.cost_basis_total is None
    assert result.market_value_total is None
    assert result.complete is False
    assert any("FX conversion" in note for note in result.completeness_notes)


@pytest.mark.parametrize("cost", [None, Decimal("0")])
def test_return_percentage_requires_positive_known_purchase_cost(cost):
    holding = SimpleNamespace(quantity=Decimal("2"), average_cost=cost,
        instrument=SimpleNamespace(canonical_symbol="AAA", exchange="NSE", asset_type="EQUITY", currency="INR", sector=None))
    portfolio = SimpleNamespace(id=uuid4(), base_currency="INR", holdings=[holding])
    result = calculate_portfolio_analytics(portfolio, [PriceInput(symbol="AAA", exchange="NSE", price="12", currency="INR", as_of=datetime.now(timezone.utc))])
    assert result.positions[0].unrealized_return_pct is None
    assert result.unrealized_return_pct is None


def test_fractional_holding_return_uses_unrounded_purchase_cost():
    holding = SimpleNamespace(quantity=Decimal("0.0001"), average_cost=Decimal("0.03"),
        instrument=SimpleNamespace(canonical_symbol="AAA", exchange="NSE", asset_type="EQUITY", currency="INR", sector=None))
    portfolio = SimpleNamespace(id=uuid4(), base_currency="INR", holdings=[holding])
    result = calculate_portfolio_analytics(portfolio, [PriceInput(symbol="AAA", exchange="NSE", price="0.04", currency="INR", as_of=datetime.now(timezone.utc))])
    assert result.positions[0].cost_basis == Decimal("0.00")
    assert result.positions[0].unrealized_return_pct == Decimal("33.33")
