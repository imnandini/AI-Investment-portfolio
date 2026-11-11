"""Daily refresh, durable closing-price history and like-for-like comparisons."""
import asyncio
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
import logging
from weakref import WeakKeyDictionary

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.integrations.daily_prices import DailyPriceError, PriceInstrument, yahoo_closes
from app.models.daily_price import DailyPrice, DailyPriceSync
from app.models.holding import Holding
from app.models.instrument import Instrument
from app.schemas.daily_prices import DailyPriceOverview, PriceComparison

IST = timezone(timedelta(hours=5, minutes=30))
LOCKS = WeakKeyDictionary()
logger = logging.getLogger(__name__)


def utcnow():
    return datetime.now(timezone.utc)


def through_date():
    # Deliberately exclude the current, possibly unfinished trading day.
    return utcnow().astimezone(IST).date() - timedelta(days=1)


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def upsert(session, model, values, keys):
    factory = pg_insert if session.bind.dialect.name == "postgresql" else sqlite_insert
    statement = factory(model).values(**values)
    session.execute(statement.on_conflict_do_update(index_elements=keys,
        set_={key: value for key, value in values.items() if key not in keys}))


async def refresh_instruments(session, instruments, settings, *, budget=18):
    if settings.daily_price_provider != "yahoo" or not instruments:
        return
    loop = asyncio.get_running_loop()
    lock = LOCKS.setdefault(loop, asyncio.Lock())
    # A foreground request must not wait behind a long background pass. The
    # stored prices remain readable and a later refresh picks up new results.
    if lock.locked():
        return
    async with lock:
        now, target = utcnow(), through_date()
        due = []
        for instrument in instruments:
            state = session.scalar(select(DailyPriceSync).where(DailyPriceSync.instrument_id == instrument.id).execution_options(populate_existing=True))
            if state and aware(state.next_check_at) > now:
                continue
            due.append((instrument.id, PriceInstrument(instrument.canonical_symbol, instrument.exchange,
                       instrument.currency, instrument.asset_type, instrument.display_name)))
        semaphore = asyncio.Semaphore(3)

        async def fetch(instrument_id, snapshot):
            async with semaphore:
                try:
                    result = await asyncio.to_thread(yahoo_closes, snapshot, target)
                    return instrument_id, result, None
                except DailyPriceError as exc:
                    return instrument_id, None, str(exc)
                except Exception:
                    return instrument_id, None, "Daily prices could not be updated. Saved prices are retained and updates will retry later."

        tasks = [asyncio.create_task(fetch(*item)) for item in due[:30]]
        if not tasks:
            return
        done, pending = await asyncio.wait(tasks, timeout=budget)
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        for task in done:
            instrument_id, result, issue = task.result()
            if result:
                for day, close in result.closes.items():
                    # Validate the adapter boundary as well as the raw provider.
                    if day > target or not close.is_finite() or close <= 0:
                        continue
                    upsert(session, DailyPrice, {"instrument_id": instrument_id, "trade_date": day,
                        "close": close, "currency": result.currency, "provider": "Yahoo Finance",
                        "provider_key": result.symbol, "exchange": result.exchange, "retrieved_at": now},
                        ["instrument_id", "trade_date"])
            tomorrow = datetime.combine(now.astimezone(IST).date() + timedelta(days=1), time.min, IST)
            next_check = now + timedelta(minutes=30) if issue else tomorrow
            if result and result.closes and max(result.closes) < target and target.weekday() < 5:
                # Yesterday's weekday bar may not have been published yet.
                # Recheck later instead of freezing an older close for a day.
                next_check = min(tomorrow, now + timedelta(hours=2))
            upsert(session, DailyPriceSync, {"instrument_id": instrument_id, "checked_at": now,
                "next_check_at": next_check,
                "requested_through": target, "status": "unavailable" if issue else "available",
                "note": issue or "Completed daily closes fetched; weekends and holidays may have no new bar."}, ["instrument_id"])
        session.commit()


async def ensure_daily_prices(session, portfolio, settings):
    await refresh_instruments(session, [h.instrument for h in portfolio.holdings], settings)


def price_overview(session, portfolio, settings):
    target = through_date()
    result = DailyPriceOverview(configured=settings.daily_price_provider == "yahoo", provider="Yahoo Finance daily closes",
                                requested_through=target, position_count=len(portfolio.holdings))
    if not result.configured:
        result.notes.append("Automatic daily prices are not connected. Existing imported or reference prices are retained.")
        return result
    if not portfolio.holdings:
        result.notes.append("Add holdings to start automatic daily closing-price updates.")
        return result
    ids = [h.instrument_id for h in portfolio.holdings]
    rows = list(session.scalars(select(DailyPrice).where(DailyPrice.instrument_id.in_(ids), DailyPrice.trade_date <= target,
                              DailyPrice.trade_date >= target - timedelta(days=45)).order_by(DailyPrice.trade_date)))
    states = list(session.scalars(select(DailyPriceSync).where(DailyPriceSync.instrument_id.in_(ids)).execution_options(populate_existing=True)))
    names = {h.instrument_id: h.instrument.display_name or h.instrument.canonical_symbol for h in portfolio.holdings}
    currencies = {h.instrument_id: h.instrument.currency for h in portfolio.holdings}
    history = {identifier: {} for identifier in ids}
    for row in rows:
        if row.currency == currencies[row.instrument_id]:
            history[row.instrument_id][row.trade_date] = row.close
    result.covered_positions = sum(bool(bars) for bars in history.values())
    if rows:
        # Show the oldest latest close in the covered set, avoiding a claim that
        # every holding has the date of the newest individual price.
        result.latest_date = min(max(bars) for bars in history.values() if bars) if result.covered_positions else None
    if states:
        result.checked_at = max(aware(state.checked_at) for state in states)
    for state in states:
        if state.status != "available":
            result.notes.append(f"{names[state.instrument_id]}: {state.note}")
    missing_states = set(ids) - {state.instrument_id for state in states}
    if missing_states:
        result.notes.append(f"Daily price updates are pending for {len(missing_states)} holdings. Reopen or refresh the portfolio shortly.")
    if result.latest_date and result.latest_date < target:
        result.notes.append(f"Latest covered closes include {result.latest_date.isoformat()}; later closes may be unavailable because of holidays, suspended trading or provider delay. Check each holding's date.")
    result.notes.append("Yahoo Finance via yfinance is an unofficial personal-use source. Daily closes are dated prices, not live quotes.")
    # No partial sum is presented as a whole-portfolio return. Foreign currencies
    # require explicit FX data, which this application does not infer.
    if result.covered_positions != len(ids) or any(c != portfolio.base_currency for c in currencies.values()):
        result.notes.append("Day/week portfolio comparisons require dated closes for every security in the base currency. No partial portfolio total or inferred FX rate is used.")
        return result
    common = set.intersection(*(set(history[identifier]) for identifier in ids))
    dates = sorted(common)
    if len(dates) < 2:
        result.notes.append("Two shared trading dates are needed for a portfolio price comparison.")
        return result
    latest = dates[-1]
    if latest < target - timedelta(days=7):
        result.notes.append("Shared historical prices are too old for a current day/week portfolio comparison.")
        return result
    week = [day for day in dates if day <= latest - timedelta(days=7)]
    pairs = [("Previous trading close", dates[-2])]
    if week:
        pairs.append(("One week earlier", week[-1]))
    else:
        result.notes.append("A shared close at least one week earlier is not available yet.")
    quantities = {h.instrument_id: h.quantity for h in portfolio.holdings}
    def value(day):
        return sum((quantities[i] * history[i][day] for i in ids), Decimal(0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    for label, previous in pairs:
        before, after = value(previous), value(latest)
        change = after - before
        pct = (change / before * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if before else None
        result.comparisons.append(PriceComparison(label=label, from_date=previous, to_date=latest,
                                 previous_value=before, latest_value=after, change=change, change_pct=pct))
    return result


async def run_daily_price_updates(engine, settings):
    """Check saved instruments every five minutes; successful pulls cache daily."""
    while True:
        try:
            with Session(engine, expire_on_commit=False) as session:
                instruments = list(session.scalars(select(Instrument).join(Holding).distinct()))
                await refresh_instruments(session, instruments, settings, budget=30)
        except asyncio.CancelledError:
            raise
        except Exception:
            # Keep the worker alive without logging payloads or private holdings.
            logger.warning("Daily price refresh failed; another check will run later.")
        await asyncio.sleep(300)
