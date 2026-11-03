from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from app.analytics.models import HoldingAnalytics, MixEntry, PortfolioAnalytics, PriceInput
from app.models.portfolio import Portfolio


CENT = Decimal("0.01")
PERCENT = Decimal("0.01")
STALE_AFTER = timedelta(days=7)


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _pct(part: Decimal, total: Decimal) -> Decimal:
    if total == 0:
        return Decimal("0.00")
    return (part * Decimal(100) / total).quantize(PERCENT, rounding=ROUND_HALF_UP)


def calculate_portfolio_analytics(
    portfolio: Portfolio, prices: list[PriceInput] | None = None
) -> PortfolioAnalytics:
    """Calculate holding-level and aggregate metrics without estimating missing values.

    Aggregate totals and allocations are reported only when their inputs are complete
    and denominated in the portfolio base currency. No FX conversion is inferred.
    """
    price_map: dict[tuple[str, str], PriceInput] = {}
    for price in prices or []:
        key = (price.symbol.strip().upper(), price.exchange.strip().upper())
        if key in price_map:
            raise ValueError(f"Duplicate price supplied for {key[0]} on {key[1]}.")
        price_map[key] = price

    holdings = sorted(portfolio.holdings, key=lambda holding: holding.instrument.canonical_symbol)
    positions: list[HoldingAnalytics] = []
    cost_total = Decimal(0)
    all_costs_base = True
    market_total = Decimal(0)
    all_markets_base = bool(holdings)
    asset_costs: dict[str, Decimal] = defaultdict(Decimal)
    sector_costs: dict[str, Decimal] = defaultdict(Decimal)

    for holding in holdings:
        instrument = holding.instrument
        quantity = Decimal(holding.quantity)
        average_cost = Decimal(holding.average_cost)
        if quantity <= 0 or average_cost < 0:
            raise ValueError("Holdings must have positive quantity and nonnegative average cost.")
        cost_basis = _money(quantity * average_cost)
        if instrument.currency == portfolio.base_currency:
            cost_total += cost_basis
            asset_costs[instrument.asset_type] += cost_basis
            sector_costs[instrument.sector or "Unknown"] += cost_basis
        else:
            all_costs_base = False

        quote = price_map.get((instrument.canonical_symbol.upper(), instrument.exchange.upper()))
        price_status = "missing"
        current_price = None
        market_value = None
        unrealized_pl = None
        price_as_of = None
        if quote is not None:
            if quote.currency != instrument.currency:
                price_status = "currency_mismatch"
            else:
                current_price = quote.price
                market_value = _money(quantity * quote.price)
                unrealized_pl = _money(market_value - cost_basis)
                price_as_of = quote.as_of
                if quote.as_of is None:
                    price_status = "unknown_freshness"
                elif quote.as_of < datetime.now(timezone.utc) - STALE_AFTER:
                    price_status = "stale"
                else:
                    price_status = "available"
                if instrument.currency == portfolio.base_currency and price_status == "available":
                    market_total += market_value
                else:
                    all_markets_base = False
        else:
            all_markets_base = False

        positions.append(
            HoldingAnalytics(
                symbol=instrument.canonical_symbol,
                exchange=instrument.exchange,
                asset_type=instrument.asset_type,
                sector=instrument.sector,
                currency=instrument.currency,
                quantity=quantity,
                average_cost=average_cost,
                cost_basis=cost_basis,
                current_price=current_price,
                market_value=market_value,
                unrealized_pl=unrealized_pl,
                market_allocation_pct=None,
                cost_basis_allocation_pct=None,
                price_as_of=price_as_of,
                price_status=price_status,
            )
        )

    priced_count = sum(p.current_price is not None for p in positions)
    complete = bool(holdings) and priced_count == len(holdings) and all_markets_base
    base_cost_total = _money(cost_total) if holdings and all_costs_base else None
    base_market_total = _money(market_total) if complete else None
    pl_total = (
        _money(base_market_total - base_cost_total)
        if base_market_total is not None and base_cost_total is not None
        else None
    )

    if base_market_total is not None and base_market_total > 0:
        for position in positions:
            if position.market_value is not None and position.currency == portfolio.base_currency:
                position.market_allocation_pct = _pct(position.market_value, base_market_total)
    if base_cost_total is not None and base_cost_total > 0:
        for position in positions:
            if position.currency == portfolio.base_currency:
                position.cost_basis_allocation_pct = _pct(position.cost_basis, base_cost_total)

    def build_mix(values: dict[str, Decimal]) -> list[MixEntry]:
        return [
            MixEntry(
                name=name,
                cost_basis=_money(value),
                allocation_pct=_pct(value, base_cost_total)
                if base_cost_total is not None and base_cost_total > 0
                else None,
            )
            for name, value in sorted(values.items())
        ]

    largest = None
    largest_allocation = None
    concentration_index = None
    if complete and positions:
        largest_position = max(positions, key=lambda position: position.market_value or Decimal(0))
        largest = largest_position.symbol
        largest_allocation = largest_position.market_allocation_pct
        if base_market_total and base_market_total > 0:
            concentration_index = sum(
                (position.market_value * Decimal(100) / base_market_total) ** 2
                for position in positions
                if position.market_value is not None
            ).quantize(PERCENT, rounding=ROUND_HALF_UP)

    notes: list[str] = []
    if not holdings:
        notes.append("Portfolio has no holdings.")
    if priced_count < len(holdings):
        notes.append("At least one holding has no usable matching price; market totals and allocation are incomplete.")
    if any(p.price_status == "stale" for p in positions):
        notes.append("Prices more than 7 days old are stale and excluded from market totals and allocation.")
    if any(p.price_status == "unknown_freshness" for p in positions):
        notes.append("Prices without an as-of timestamp have unknown freshness and are excluded from market totals and allocation.")
    if any(p.price_status == "currency_mismatch" for p in positions):
        notes.append("A supplied price currency does not match its instrument currency; that price was excluded.")
    if any(p.currency != portfolio.base_currency for p in positions):
        notes.append("Foreign-currency holdings are excluded from base-currency totals because FX conversion is unavailable.")
    if not all_costs_base and base_cost_total is None:
        notes.append("Base-currency cost basis totals and mix are incomplete because FX conversion is unavailable.")

    return PortfolioAnalytics(
        portfolio_id=str(portfolio.id if isinstance(portfolio.id, UUID) else portfolio.id),
        base_currency=portfolio.base_currency,
        methodology=(
            "Cost basis = quantity × average cost. Market value = quantity × user-supplied price. "
            "Unrealized P/L = market value − cost basis. Market allocation uses complete base-currency market value; "
            "asset and sector mix use base-currency cost basis. Prices older than 7 days or without an as-of timestamp "
            "are excluded from aggregate market metrics. Concentration index is the sum of squared "
            "market-allocation percentages (0–10,000). No FX conversion or missing-price estimate is applied."
        ),
        cost_basis_total=base_cost_total,
        market_value_total=base_market_total,
        unrealized_pl_total=pl_total,
        largest_holding_symbol=largest,
        largest_holding_allocation_pct=largest_allocation,
        concentration_index=concentration_index,
        asset_mix=build_mix(asset_costs),
        sector_mix=build_mix(sector_costs),
        positions=positions,
        priced_position_count=priced_count,
        unpriced_position_count=len(holdings) - priced_count,
        complete=complete,
        completeness_notes=notes,
    )
