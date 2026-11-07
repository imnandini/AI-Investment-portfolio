from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.models.data_source import DataSourceRecord
from app.schemas.financial_data import CompanyProfile, PriceQuote, ProviderResult
from app.services.financial_data import create_financial_data_service


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def freshness(result, kind, now):
    if result.status != "available":
        return "unavailable"
    if kind != "price":
        return "available"
    as_of = result.data.as_of
    if as_of is None:
        return "unknown_freshness"
    return "stale" if aware(as_of) < now - timedelta(days=7) else "available"


async def cached_lookup(session, settings, kind, symbol, exchange):
    now = datetime.now(timezone.utc)
    symbol, exchange = symbol.upper(), exchange.upper()
    provider = settings.financial_data_provider.strip().lower()
    schema = ProviderResult[CompanyProfile if kind == "profile" else PriceQuote]
    record = session.scalar(select(DataSourceRecord).where(
        DataSourceRecord.provider == provider, DataSourceRecord.kind == kind,
        DataSourceRecord.symbol == symbol, DataSourceRecord.exchange == exchange))
    if record and aware(record.expires_at) > now:
        result = schema.model_validate(record.payload)
        return {"result": result, "data_status": freshness(result, kind, now), "cache_status": "fresh", "retrieved_at": record.retrieved_at, "expires_at": record.expires_at}
    service = create_financial_data_service(settings)
    result = await (service.get_company_profile(symbol, exchange) if kind == "profile" else service.get_price(symbol, exchange))
    # Never present an expired success as a fresh quote after an upstream error.
    ttl = timedelta(minutes=15 if result.status == "available" else 1)
    if record is None:
        record = DataSourceRecord(provider=provider, kind=kind, symbol=symbol, exchange=exchange)
        session.add(record)
    record.payload = result.model_dump(mode="json")
    record.retrieved_at, record.expires_at = now, now + ttl
    try:
        session.commit()
    except IntegrityError:
        session.rollback()  # Concurrent cache fills need not fail the lookup.
    return {"result": result, "data_status": freshness(result, kind, now), "cache_status": "refreshed", "retrieved_at": now, "expires_at": now + ttl}
