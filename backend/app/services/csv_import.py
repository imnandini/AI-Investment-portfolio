import csv
import io
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.holding import Holding
from app.models.instrument import Instrument
from app.models.portfolio import Portfolio
from app.schemas.imports import ImportRowError
from app.schemas.portfolio import HoldingCreate
from app.services.portfolios import PortfolioNotFoundError


MAX_CSV_BYTES = 1_000_000
MAX_CSV_ROWS = 500
REQUIRED_COLUMNS = {"symbol", "quantity", "average_cost"}
ALLOWED_COLUMNS = REQUIRED_COLUMNS | {
    "exchange", "asset_type", "currency", "sector", "purchase_date"
}


class CsvImportFormatError(Exception):
    pass


@dataclass
class ParsedHoldingRow:
    row_number: int
    holding: HoldingCreate


def parse_holdings_csv(content: bytes) -> tuple[list[ParsedHoldingRow], list[ImportRowError]]:
    if len(content) > MAX_CSV_BYTES:
        raise CsvImportFormatError("CSV file exceeds the 1 MB upload limit.")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise CsvImportFormatError("CSV must be encoded as UTF-8.") from None
    reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
    try:
        fieldnames = reader.fieldnames
    except csv.Error:
        raise CsvImportFormatError("CSV syntax is invalid.") from None
    if not fieldnames:
        raise CsvImportFormatError("CSV must include a header row.")
    headers = [header.strip().lower() if header else "" for header in fieldnames]
    if len(headers) != len(set(headers)):
        raise CsvImportFormatError("CSV contains duplicate column names.")
    missing = REQUIRED_COLUMNS - set(headers)
    if missing:
        raise CsvImportFormatError("CSV is missing required columns: " + ", ".join(sorted(missing)))
    unknown = set(headers) - ALLOWED_COLUMNS
    if unknown:
        raise CsvImportFormatError("CSV contains unsupported columns: " + ", ".join(sorted(unknown)))

    parsed: list[ParsedHoldingRow] = []
    errors: list[ImportRowError] = []
    try:
        for row_number, raw in enumerate(reader, start=2):
            if row_number - 1 > MAX_CSV_ROWS:
                raise CsvImportFormatError(f"CSV exceeds the {MAX_CSV_ROWS} row limit.")
            if None in raw:
                errors.append(ImportRowError(row=row_number, message="Row has more values than the header."))
                continue
            values = {key.strip().lower(): (value or "").strip() for key, value in raw.items()}
            if not any(values.values()):
                continue
            try:
                quantity = Decimal(values["quantity"])
            except InvalidOperation:
                errors.append(ImportRowError(row=row_number, field="quantity", message="Must be a decimal number."))
                continue
            try:
                average_cost = Decimal(values["average_cost"])
            except InvalidOperation:
                errors.append(ImportRowError(row=row_number, field="average_cost", message="Must be a decimal number."))
                continue
            purchase_date = values.get("purchase_date") or None
            if purchase_date:
                try:
                    purchase_date = date.fromisoformat(purchase_date)
                except ValueError:
                    errors.append(ImportRowError(row=row_number, field="purchase_date", message="Use the YYYY-MM-DD format."))
                    continue
            try:
                payload = HoldingCreate(
                    symbol=values.get("symbol", ""),
                    exchange=values.get("exchange") or None,
                    asset_type=values.get("asset_type") or "EQUITY",
                    currency=values.get("currency") or "INR",
                    sector=values.get("sector") or None,
                    quantity=quantity,
                    average_cost=average_cost,
                    purchase_date=purchase_date,
                )
            except ValidationError as exc:
                for detail in exc.errors():
                    errors.append(ImportRowError(
                        row=row_number,
                        field=".".join(str(part) for part in detail["loc"]) or None,
                        message=detail["msg"],
                    ))
                continue
            parsed.append(ParsedHoldingRow(row_number=row_number, holding=payload))
    except csv.Error:
        raise CsvImportFormatError("CSV syntax is invalid.") from None
    return parsed, errors


def import_holdings_csv(
    session: Session, user_id, portfolio_id, content: bytes
) -> tuple[list[Holding], list[ImportRowError]]:
    parsed, errors = parse_holdings_csv(content)
    portfolio = session.scalar(
        select(Portfolio).where(Portfolio.id == portfolio_id, Portfolio.user_id == user_id)
    )
    if portfolio is None:
        raise PortfolioNotFoundError

    existing = session.scalars(
        select(Holding)
        .where(Holding.portfolio_id == portfolio_id)
        .options(selectinload(Holding.instrument))
    ).all()
    existing_keys = {
        (holding.instrument.canonical_symbol, holding.instrument.exchange): holding
        for holding in existing
    }
    seen: set[tuple[str, str]] = set()
    imported: list[Holding] = []
    for row in parsed:
        data = row.holding
        exchange = data.exchange or "UNKNOWN"
        key = (data.symbol, exchange)
        if key in seen:
            errors.append(ImportRowError(row=row.row_number, field="symbol", message="Duplicate symbol and exchange in this CSV."))
            continue
        seen.add(key)
        if key in existing_keys:
            errors.append(ImportRowError(row=row.row_number, field="symbol", message="This symbol and exchange are already in the portfolio."))
            continue
        instrument = session.scalar(
            select(Instrument).where(
                Instrument.canonical_symbol == data.symbol,
                Instrument.exchange == exchange,
            )
        )
        if instrument is not None and (
            instrument.asset_type != data.asset_type
            or instrument.currency != data.currency
            or (data.sector and instrument.sector and instrument.sector != data.sector)
        ):
            errors.append(ImportRowError(row=row.row_number, field="symbol", message="Instrument details conflict with the existing symbol and exchange."))
            continue
        if instrument is None:
            instrument = Instrument(
                canonical_symbol=data.symbol,
                exchange=exchange,
                asset_type=data.asset_type,
                currency=data.currency,
                sector=data.sector,
            )
            session.add(instrument)
            session.flush()
        elif data.sector and instrument.sector is None:
            instrument.sector = data.sector
        holding = Holding(
            portfolio_id=portfolio_id,
            instrument_id=instrument.id,
            quantity=data.quantity,
            average_cost=data.average_cost,
            purchase_date=data.purchase_date,
        )
        session.add(holding)
        imported.append(holding)

    try:
        session.commit()
    except Exception:
        session.rollback()
        raise
    for holding in imported:
        session.refresh(holding)
        session.refresh(holding.instrument)
    return imported, errors
