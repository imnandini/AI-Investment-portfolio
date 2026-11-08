"""Normalize provider holdings and apply a reviewed, incremental import atomically."""
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import json
import re

from pydantic import ValidationError
from sqlalchemy import delete, select

from app.analytics.models import PriceInput
from app.integrations.indmoney import IndmoneyError, aware, now, seal, unseal
from app.models.holding import Holding
from app.models.indmoney import IndmoneyBalance, IndmoneyConnection, IndmoneyPreview, IndmoneyPrice
from app.models.instrument import Instrument
from app.models.portfolio import Portfolio
from app.schemas.portfolio import HoldingCreate
from app.services.prices import require_portfolio

PRECISION = Decimal("0.0000000001")


def display_name(row):
    value = first(row, "investment", "company_name", "display_name", "name")
    return value.strip()[:200] if isinstance(value, str) and value.strip() else None


def normalize_balance(row, asset_type):
    name = display_name(row)
    if not name:
        raise ValueError("missing account name")
    market_value = number(first(row, "market_value", "current_value", "balance"))
    if market_value is None or market_value < 0:
        raise ValueError("missing or invalid account balance")
    invested = number(first(row, "invested_amount", "invested_value", "total_investment", "cost_basis"))
    if invested is not None and invested < 0:
        raise ValueError("negative invested amount")
    currency = first(row, "currency", "currency_code") or "INR"
    if not isinstance(currency, str) or not re.fullmatch(r"[A-Za-z]{3}", currency):
        raise ValueError("invalid currency")
    # INDmoney supplies no identifier for EPF. This is an account reference,
    # scoped to the portfolio, not an inferred stock symbol or account number.
    identity = first(row, "investment_code", "account_id") or name.casefold()
    asset_key = asset_type + "-" + hashlib.sha256(str(identity).encode()).hexdigest()[:24]
    as_of = first(row, "as_of", "updated_at")
    if as_of is not None:
        try:
            as_of = datetime.fromisoformat(str(as_of).replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("invalid balance timestamp") from None
        if as_of.utcoffset() is None or as_of > now() + timedelta(minutes=5):
            raise ValueError("invalid balance timestamp")
    return {"kind": "balance", "symbol": asset_key, "display_name": name, "asset_type": asset_type,
            "currency": currency.upper(), "market_value": str(market_value),
            "invested_amount": str(invested) if invested is not None else None,
            "as_of": as_of.isoformat() if as_of else None}


def keys(row):
    return {re.sub(r"(?<!^)(?=[A-Z])", "_", str(key)).lower(): value for key, value in row.items()}


def first(row, *names):
    return next((row[name] for name in names if row.get(name) is not None), None)


def number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value).replace(",", "").strip())
        if not result.is_finite() or abs(result) >= Decimal("1e14"):
            return None
        return result.quantize(PRECISION, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return None


def unwrap(payload):
    """Only recognized holdings envelopes; prose and arbitrary arrays are rejected."""
    for _ in range(8):
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except ValueError:
                break
        if isinstance(payload, list):
            return payload
        if not isinstance(payload, dict):
            break
        obj = keys(payload)
        if obj.get("error") or obj.get("success") is False or obj.get("status") in ("error", "failed"):
            raise IndmoneyError("INDmoney reported a holdings error. No holdings were changed.")
        if obj.get("has_more") or obj.get("next_cursor") or obj.get("next_page") or obj.get("next_page_token"):
            raise IndmoneyError("INDmoney returned a paginated snapshot. Import was stopped to avoid silently omitting holdings.", 422)
        child = first(obj, "holdings", "positions", "items", "data", "result", "networth_holdings")
        if child is None:
            break
        count = first(obj, "total_count", "total_records", "total")
        if isinstance(child, list) and isinstance(count, (int, float)) and count > len(child):
            raise IndmoneyError("INDmoney returned an incomplete snapshot. No holdings were changed.", 422)
        payload = child
    raise IndmoneyError("INDmoney's holdings response format is unsupported. No holdings were changed.", 422)


def normalize(payload, asset_type):
    rows = unwrap(payload)
    if len(rows) > 1000:
        raise IndmoneyError("INDmoney returned more than 1,000 positions. Choose a smaller asset group.", 422)
    grouped, warnings = {}, []
    for index, original in enumerate(rows, 1):
        try:
            if not isinstance(original, dict):
                raise ValueError("position is not an object")
            row = keys(original)
            if asset_type in ("EPF", "PPF"):
                item = normalize_balance(row, asset_type)
                key = (item["symbol"], "balance")
                if key in grouped:
                    raise IndmoneyError("INDmoney returned indistinguishable PF accounts. Import was stopped to avoid combining different balances.", 422)
                grouped[key] = item
                continue
            row_asset_type = first(row, "asset_type", "asset_class") or asset_type
            if not isinstance(row_asset_type, str):
                raise ValueError("invalid asset type")
            row_asset_type = row_asset_type.strip().upper().replace(" ", "_")
            # The holdings payload labels both markets STOCK; the requested MCP
            # asset group disambiguates their currency and instrument category.
            if row_asset_type == "STOCK" and asset_type in ("IND_STOCK", "US_STOCK"):
                row_asset_type = asset_type
            symbol = first(row, "symbol", "trading_symbol", "tradingsymbol", "ticker", "isin", "scheme_code", "investment_code")
            if not isinstance(symbol, (str, int)) or not str(symbol).strip():
                raise ValueError("missing symbol, ISIN, scheme code or investment code")
            quantity = number(first(row, "quantity", "units", "holding_quantity", "total_units"))
            if quantity is None or quantity <= 0:
                raise ValueError("missing or non-positive quantity")
            currency = first(row, "currency", "currency_code")
            if currency is None:
                currency = "USD" if row_asset_type in ("US_STOCK", "US_STOCKS") else "INR" if row_asset_type in ("IND_STOCK", "INDIAN_STOCKS", "MUTUAL_FUND", "MF") else None
            if currency is None:
                raise ValueError("missing currency for this asset type")
            average = number(first(row, "average_cost", "average_price", "avg_price", "average_buy_price", "avg_cost"))
            invested = number(first(row, "invested_amount", "invested_value", "total_investment", "cost_basis"))
            if average is None and invested is not None and invested >= 0:
                average = (invested / quantity).quantize(PRECISION, rounding=ROUND_HALF_UP)
            if average is not None and average < 0:
                raise ValueError("negative purchase cost")
            validated = HoldingCreate(symbol=str(symbol), exchange=first(row, "exchange", "stock_exchange") or "UNKNOWN",
                asset_type="MUTUAL_FUND" if row_asset_type in ("MUTUAL_FUND", "MF") else "EQUITY" if row_asset_type in ("IND_STOCK", "US_STOCK", "INDIAN_STOCKS", "US_STOCKS") else row_asset_type,
                currency=currency, sector=row.get("sector"), quantity=quantity, average_cost=average or Decimal(0))
            item = validated.model_dump(mode="json")
            item["display_name"] = display_name(row)
            item["average_cost"] = str(average) if average is not None else None
            item["price"] = None
            price = number(first(row, "unit_price", "current_price", "ltp", "nav", "price"))
            if price is not None and price > 0:
                try:
                    parsed_price = PriceInput(symbol=validated.symbol, exchange=validated.exchange, price=price,
                        currency=validated.currency, as_of=first(row, "as_of", "price_as_of", "updated_at"))
                    if parsed_price.as_of and parsed_price.as_of > now() + timedelta(minutes=5):
                        raise ValueError("future price timestamp")
                    item["price"] = parsed_price.model_dump(mode="json")
                except (ValueError, ValidationError):
                    warnings.append(f"Row {index}: price omitted because its timestamp or value is invalid.")
            key = (item["symbol"], item["exchange"])
            previous = grouped.get(key)
            if previous:
                if (previous["currency"], previous["asset_type"]) != (item["currency"], item["asset_type"]):
                    raise IndmoneyError("INDmoney returned conflicting instrument identities. No holdings were changed.", 422)
                total_quantity = Decimal(previous["quantity"]) + quantity
                if previous["average_cost"] is not None and average is not None:
                    total_cost = Decimal(previous["quantity"]) * Decimal(previous["average_cost"]) + quantity * average
                    previous["average_cost"] = str((total_cost / total_quantity).quantize(PRECISION, rounding=ROUND_HALF_UP))
                else:
                    previous["average_cost"] = None
                previous["quantity"] = str(total_quantity)
                if previous["price"] != item["price"]:
                    previous["price"] = None
            else:
                grouped[key] = item
        except ValidationError as error:
            # Include field names only: provider values may contain account data.
            fields = sorted({str(issue["loc"][0]) for issue in error.errors() if issue["loc"]})
            warnings.append(f"Row {index}: skipped because these fields are invalid: {', '.join(fields)}.")
        except ValueError as error:
            warnings.append(f"Row {index}: skipped because {error}.")
        except TypeError:
            warnings.append(f"Row {index}: skipped because a holding field has an unsupported format.")
    result = list(grouped.values())
    for item in result:
        if item.get("kind") == "balance":
            continue
        if Decimal(item["quantity"]) >= Decimal("1e14"):
            raise IndmoneyError("An aggregated INDmoney position exceeds the supported quantity limit.", 422)
        if item["average_cost"] is None:
            warnings.append(f"{item['symbol']}: purchase cost is unknown; cost basis and P/L will remain unavailable.")
    return result, warnings


def preview_import(session, user_id, portfolio_id, settings, payload, asset_type):
    portfolio = require_portfolio(session, user_id, portfolio_id)
    rows, warnings = normalize(payload, asset_type)
    manual = {(h.instrument.canonical_symbol, h.instrument.exchange) for h in portfolio.holdings if h.source != "indmoney"}
    for row in rows:
        row["conflict"] = row.get("kind") != "balance" and (row["symbol"], row["exchange"]) in manual
        if row["conflict"]:
            warnings.append(f"{row['symbol']}: existing manual/CSV holding will be preserved and skipped.")
    # Retain just the latest preview for this portfolio, and purge expired previews.
    session.execute(delete(IndmoneyPreview).where(IndmoneyPreview.user_id == user_id,
        (IndmoneyPreview.expires_at <= now()) | (IndmoneyPreview.portfolio_id == portfolio_id)).execution_options(synchronize_session=False))
    preview = IndmoneyPreview(user_id=user_id, portfolio_id=portfolio_id,
        payload=seal(settings, {"rows": rows, "warnings": warnings}), expires_at=now() + timedelta(minutes=10))
    session.add(preview)
    session.commit()
    return {"preview_id": preview.id, "rows": rows, "warnings": warnings, "expires_at": preview.expires_at,
            "mode": "Updates matching INDmoney holdings and adds new positions. Manual/CSV holdings and positions absent from this import are preserved."}


def apply_import(session, user_id, portfolio_id, preview_id, settings):
    require_portfolio(session, user_id, portfolio_id)
    # Serialize portfolio imports, including two different preview requests.
    session.scalar(select(Portfolio).where(Portfolio.id == portfolio_id, Portfolio.user_id == user_id).with_for_update())
    preview = session.scalar(select(IndmoneyPreview).where(IndmoneyPreview.id == preview_id,
        IndmoneyPreview.user_id == user_id, IndmoneyPreview.portfolio_id == portfolio_id).with_for_update())
    connection = session.get(IndmoneyConnection, user_id)
    if not connection or not connection.credentials:
        raise IndmoneyError("Reconnect INDmoney before importing.", 409)
    if not preview or aware(preview.expires_at) <= now():
        raise IndmoneyError("This import preview expired or was already used. Preview holdings again.", 409)
    data = unseal(settings, preview.payload)
    claimed = session.execute(delete(IndmoneyPreview).where(IndmoneyPreview.id == preview_id,
        IndmoneyPreview.user_id == user_id, IndmoneyPreview.expires_at > now()).execution_options(synchronize_session=False))
    if claimed.rowcount != 1:
        raise IndmoneyError("This preview was already imported or expired.", 409)
    added = updated = skipped = 0
    warnings = list(data["warnings"])
    for item in data["rows"]:
        if item.get("kind") == "balance":
            balance = session.get(IndmoneyBalance, (portfolio_id, item["symbol"]))
            if balance is None:
                balance = IndmoneyBalance(portfolio_id=portfolio_id, asset_key=item["symbol"])
                session.add(balance)
                added += 1
            else:
                updated += 1
            balance.payload = json.dumps({k: v for k, v in item.items() if k != "conflict"})
            balance.imported_at = now()
            continue
        instrument = session.scalar(select(Instrument).where(Instrument.canonical_symbol == item["symbol"], Instrument.exchange == item["exchange"]))
        if instrument is not None and (instrument.asset_type.upper(), instrument.currency) != (item["asset_type"].upper(), item["currency"]):
            skipped += 1
            warnings.append(f"{item['symbol']}: instrument currency or asset type conflicts with an existing instrument.")
            continue
        if instrument is None:
            instrument = Instrument(canonical_symbol=item["symbol"], exchange=item["exchange"],
                asset_type=item["asset_type"], currency=item["currency"], sector=item["sector"])
            session.add(instrument)
            session.flush()
        holding = session.scalar(select(Holding).where(Holding.portfolio_id == portfolio_id, Holding.instrument_id == instrument.id))
        if holding is not None and holding.source != "indmoney":
            skipped += 1
            continue
        if holding is None:
            holding = Holding(portfolio_id=portfolio_id, instrument_id=instrument.id, source="indmoney")
            session.add(holding)
            added += 1
        else:
            updated += 1
        if item.get("display_name"):
            instrument.display_name = item["display_name"]
        holding.quantity = Decimal(item["quantity"])
        holding.average_cost = Decimal(item["average_cost"]) if item["average_cost"] is not None else None
        quote = session.get(IndmoneyPrice, (portfolio_id, item["symbol"], item["exchange"]))
        if item["price"]:
            if quote is None:
                quote = IndmoneyPrice(portfolio_id=portfolio_id, symbol=item["symbol"], exchange=item["exchange"])
                session.add(quote)
            quote.payload = json.dumps(item["price"])
        elif quote is not None:
            session.delete(quote)
    connection.last_sync_at = now()
    session.commit()
    session.expire_all()
    return {"added": added, "updated": updated, "skipped": skipped, "warnings": warnings}


def list_balances(session, user_id, portfolio_id):
    require_portfolio(session, user_id, portfolio_id)
    records = session.scalars(select(IndmoneyBalance).where(IndmoneyBalance.portfolio_id == portfolio_id)
        .order_by(IndmoneyBalance.asset_key))
    return [{**json.loads(row.payload), "imported_at": aware(row.imported_at)} for row in records]
