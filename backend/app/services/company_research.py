"""Bounded provider work and durable, public-company snapshot cache."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import threading

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.integrations.company_fundamentals import CompanyResearchError, public_query, yahoo_company_search, yahoo_company_snapshot
from app.models.data_source import DataSourceRecord
from app.schemas.company_research import CompanySearch, CompanySnapshot
from app.services.market_data import aware

WORKERS = ThreadPoolExecutor(max_workers=2, thread_name_prefix="company-research")
SLOTS = threading.BoundedSemaphore(2)


async def provider_call(function, *args):
    # Reject excess work instead of allowing an unbounded queue of timed-out requests.
    if not SLOTS.acquire(blocking=False):
        raise CompanyResearchError("Company research is busy. Please retry shortly.")
    try:
        future = WORKERS.submit(function, *args)
    except Exception:
        SLOTS.release()
        raise
    future.add_done_callback(lambda _: SLOTS.release())
    try:
        return await asyncio.wait_for(asyncio.wrap_future(future), timeout=20)
    except CompanyResearchError:
        raise
    except Exception:
        raise CompanyResearchError("Yahoo Finance is temporarily unavailable or limiting requests. Try again later or open Screener.") from None


async def search_companies(query, settings):
    if settings.company_research_provider != "yahoo":
        return CompanySearch(status="unavailable", note="Company research is disabled. Set COMPANY_RESEARCH_PROVIDER=yahoo for personal-use company search.")
    try:
        matches = await provider_call(yahoo_company_search, public_query(query))
        return CompanySearch(status="available", matches=matches,
            note="Choose the correct company and exchange." if matches else "No Indian stock matched. Try the full company name or NSE/BSE ticker.")
    except CompanyResearchError as exc:
        return CompanySearch(status="unavailable", note=str(exc))


async def company_snapshot(session, settings, symbol, exchange):
    now = datetime.now(timezone.utc)
    symbol, exchange = symbol.upper(), exchange.upper()
    ticker = symbol + (".NS" if exchange == "NSE" else ".BO")
    from urllib.parse import quote
    result = CompanySnapshot(status="unavailable", symbol=symbol, exchange=exchange, retrieved_at=now,
        source_url=f"https://finance.yahoo.com/quote/{quote(ticker, safe='')}/",
        screener_url=f"https://www.screener.in/company/{quote(symbol, safe='')}/consolidated/")
    if settings.company_research_provider != "yahoo":
        result.notes = ["Company research is disabled. Set COMPANY_RESEARCH_PROVIDER=yahoo for personal use."]
        return result
    try:
        public_query(symbol)
    except CompanyResearchError as exc:
        result.notes = [str(exc)]
        return result
    record = session.scalar(select(DataSourceRecord).where(DataSourceRecord.provider == "yahoo",
        DataSourceRecord.kind == "fundamentals", DataSourceRecord.symbol == symbol, DataSourceRecord.exchange == exchange))
    if record and aware(record.expires_at) > now:
        return CompanySnapshot.model_validate(record.payload).model_copy(update={"cached": True})
    try:
        data = await provider_call(yahoo_company_snapshot, symbol, exchange)
        result = CompanySnapshot(**{**result.model_dump(), **data, "status": "available"})
    except CompanyResearchError as exc:
        result.notes = [str(exc)]
    # Never substitute an expired success for a failed fetch.
    fetched_at = datetime.now(timezone.utc)
    result.retrieved_at = fetched_at
    result.expires_at = fetched_at + timedelta(hours=6) if result.status == "available" else fetched_at + timedelta(minutes=1)
    if record is None:
        record = DataSourceRecord(provider="yahoo", kind="fundamentals", symbol=symbol, exchange=exchange)
        session.add(record)
    record.payload = result.model_dump(mode="json")
    record.retrieved_at, record.expires_at = fetched_at, result.expires_at
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
    return result
