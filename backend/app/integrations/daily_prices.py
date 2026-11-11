"""Personal-use daily closes through yfinance. No portfolio amounts leave the app."""
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
import re


class DailyPriceError(Exception):
    """Only fixed, safe messages may cross the provider boundary."""


@dataclass(frozen=True)
class PriceInstrument:
    symbol: str
    exchange: str
    currency: str
    asset_type: str
    name: str | None = None


@dataclass(frozen=True)
class ClosingPrices:
    symbol: str
    exchange: str
    currency: str
    closes: dict[date, Decimal]


def normalized_name(value):
    terms = re.findall(r"[a-z0-9]+", (value or "").casefold())
    while terms and terms[-1] in {"ltd", "limited", "inc", "incorporated", "corp", "corporation", "plc"}:
        terms.pop()
    return " ".join(terms)


def resolve_ticker(instrument, search):
    symbol = instrument.symbol.upper()
    # Genuine exchange symbols are mapped directly. Internal INDmoney references
    # and ISINs are never treated as exchange tickers.
    internal = bool(re.fullmatch(r"INDS\d+|IN[A-Z0-9]{10}", symbol))
    if not internal and instrument.exchange in ("NSE", "BSE"):
        suffix = ".NS" if instrument.exchange == "NSE" else ".BO"
        return symbol if symbol.endswith(suffix) else symbol + suffix
    if not internal and instrument.exchange in ("NASDAQ", "NYSE", "AMEX", "NYSEARCA", "US") and instrument.currency == "USD":
        return symbol
    if not instrument.name:
        raise DailyPriceError("A verified exchange symbol or full company name is needed for automatic prices.")
    # Search only the public company name, never an internal account/position ID.
    quotes = search(instrument.name)
    candidates = []
    for item in quotes:
        ticker = item.get("symbol", "")
        if item.get("quoteType") not in ("EQUITY", "ETF"):
            continue
        if normalized_name(instrument.name) not in {normalized_name(item.get("longname")), normalized_name(item.get("shortname"))}:
            continue
        if instrument.currency == "INR" and not ticker.endswith((".NS", ".BO")):
            continue
        if instrument.currency == "USD" and ticker.endswith((".NS", ".BO")):
            continue
        if instrument.exchange == "NSE" and not ticker.endswith(".NS"):
            continue
        if instrument.exchange == "BSE" and not ticker.endswith(".BO"):
            continue
        candidates.append(ticker)
    # Prefer NSE only among exact company-name matches, never a fuzzy search hit.
    preferred = sorted(set(t for t in candidates if t.endswith(".NS"))) if instrument.currency == "INR" and instrument.exchange == "UNKNOWN" else []
    candidates = preferred or sorted(set(candidates))
    if len(candidates) != 1:
        raise DailyPriceError("No unique company match was found. Check this holding's company name and exchange symbol.")
    return candidates[0]


def yahoo_closes(instrument: PriceInstrument, through: date) -> ClosingPrices:
    """Blocking provider call; the service runs this in a bounded worker thread."""
    if instrument.asset_type.upper() not in ("EQUITY", "STOCK", "ETF"):
        raise DailyPriceError("Automatic daily stock prices do not cover this asset type. Its imported balance or NAV is retained.")
    if instrument.currency not in ("INR", "USD"):
        raise DailyPriceError("Automatic daily prices currently support INR and USD securities.")
    import yfinance as yf
    from yfinance.exceptions import YFRateLimitError

    try:
        def search(name):
            return yf.Search(name, max_results=10, news_count=0, enable_fuzzy_query=False, timeout=5).quotes

        symbol = resolve_ticker(instrument, search)
        ticker = yf.Ticker(symbol)
        history = ticker.history(start=(through - timedelta(days=45)).isoformat(),
                                 end=(through + timedelta(days=1)).isoformat(), interval="1d",
                                 auto_adjust=False, actions=True, repair=False, timeout=6, raise_errors=True)
        metadata = ticker.get_history_metadata()
        if metadata.get("currency") != instrument.currency:
            raise DailyPriceError("The price provider's currency does not match this holding. No price was saved.")
        expected_exchange = "NSI" if symbol.endswith(".NS") else "BSE" if symbol.endswith(".BO") else None
        if expected_exchange and metadata.get("exchangeName") != expected_exchange:
            raise DailyPriceError("The price provider's exchange does not match the resolved ticker.")
        venue = {"NYQ": "NYSE", "NMS": "NASDAQ", "NGM": "NASDAQ", "NCM": "NASDAQ", "ASE": "AMEX", "PCX": "NYSEARCA"}.get(metadata.get("exchangeName"))
        if instrument.exchange in ("NYSE", "NASDAQ", "AMEX", "NYSEARCA") and venue != instrument.exchange:
            raise DailyPriceError("The price provider's exchange does not match this holding's exchange.")
        if metadata.get("instrumentType") not in ("EQUITY", "ETF"):
            raise DailyPriceError("The resolved ticker is not a stock or ETF.")
        closes = {}
        for timestamp, row in history.iterrows():
            day = timestamp.date()
            if day > through or day < through - timedelta(days=45):
                continue
            try:
                value = Decimal(str(row["Close"]))
            except (InvalidOperation, TypeError, ValueError):
                continue
            if value.is_finite() and value > 0:
                closes[day] = value.quantize(Decimal("0.0000000001"))
        if not closes:
            raise DailyPriceError("No completed daily closing prices were returned for this holding.")
        exchange = "NSE" if symbol.endswith(".NS") else "BSE" if symbol.endswith(".BO") else venue or metadata.get("exchangeName", instrument.exchange)
        return ClosingPrices(symbol, exchange, instrument.currency, closes)
    except DailyPriceError:
        raise
    except YFRateLimitError:
        raise DailyPriceError("Yahoo Finance temporarily limited requests. Saved prices are retained; updates will retry later.") from None
    except Exception:
        raise DailyPriceError("Yahoo Finance could not supply a verified daily price. Saved prices are retained; updates will retry later.") from None
