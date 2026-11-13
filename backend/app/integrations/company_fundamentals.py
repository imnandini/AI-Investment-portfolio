"""On-demand personal research. Only public company names/tickers leave the app."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import re

from app.schemas.company_research import CompanyMatch, CompanyStatement, StatementRow


class CompanyResearchError(Exception):
    """Fixed provider messages only; upstream exceptions may contain credentials."""


def number(value, multiplier=1):
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value)) * multiplier
        return format(result, "f") if result.is_finite() else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def public_query(value):
    query = " ".join(value.split())
    if not 2 <= len(query) <= 200:
        raise CompanyResearchError("Enter between 2 and 200 characters for the company name or ticker.")
    if re.fullmatch(r"INDS\d+|IN[A-Z0-9]{10}|(?:EPF|PPF)-.*", query, re.I):
        raise CompanyResearchError("Search by public company name or exchange ticker, not an account or holding reference.")
    if "://" in query or "/" in query:
        raise CompanyResearchError("Enter a company name or ticker. Paste Screener company links in the research search box.")
    return query


def yahoo_company_search(query):
    import yfinance as yf

    query = public_query(query)
    quotes = yf.Search(query, max_results=12, news_count=0, enable_fuzzy_query=False, timeout=5).quotes
    matches = {}
    for quote in quotes:
        ticker = quote.get("symbol", "")
        if quote.get("quoteType") != "EQUITY" or not re.fullmatch(r"[A-Za-z0-9&._-]{1,32}\.(NS|BO)", ticker):
            continue
        exchange = "NSE" if ticker.endswith(".NS") else "BSE"
        symbol = ticker[:-3]
        name = quote.get("longname") or quote.get("shortname")
        if name:
            matches[(symbol, exchange)] = CompanyMatch(symbol=symbol, exchange=exchange, name=str(name)[:200])
    return list(matches.values())[:10]


def statement(frame, title, currency, fields):
    # Missing provider cells remain unknown, including NaN and infinity.
    if frame is None or frame.empty:
        return None
    columns = sorted(frame.columns, reverse=True)[:4]
    rows = []
    for label, keys in fields:
        key = next((key for key in keys if key in frame.index), None)
        rows.append(StatementRow(label=label, unit="per_share" if key == "DilutedEPS" else "currency",
            values=[number(frame.loc[key, col]) if key else None for col in columns]))
    if not any(value is not None for row in rows for value in row.values):
        return None
    return CompanyStatement(title=title, currency=currency, periods=[col.date().isoformat() for col in columns], rows=rows)


def yahoo_company_snapshot(symbol, exchange):
    import yfinance as yf

    ticker_symbol = symbol + (".NS" if exchange == "NSE" else ".BO")
    ticker = yf.Ticker(ticker_symbol)
    info = ticker.get_info()
    expected_exchange = "NSI" if exchange == "NSE" else "BSE"
    if (info.get("symbol", "").upper() != ticker_symbol or info.get("exchange") != expected_exchange
            or info.get("quoteType") != "EQUITY" or info.get("currency") != "INR"):
        raise CompanyResearchError("The provider could not verify this Indian stock's ticker, exchange and currency. Choose a company from search results.")
    name = info.get("longName") or info.get("shortName")
    if not name:
        raise CompanyResearchError("The provider did not return a company profile for this ticker.")
    metric_fields = [
        ("Market capitalisation", "marketCap", "INR", "Market snapshot", 1),
        ("P/E", "trailingPE", "times", "Trailing 12 months", 1),
        ("Price / book", "priceToBook", "times", "Provider's latest book value", 1),
        ("Return on equity", "returnOnEquity", "%", "Trailing 12 months", 100),
        ("Net profit margin", "profitMargins", "%", "Trailing 12 months", 100),
        ("Revenue", "totalRevenue", "INR", "Trailing 12 months", 1),
        ("Net income to common shareholders", "netIncomeToCommon", "INR", "Trailing 12 months", 1),
        ("Total debt", "totalDebt", "INR", "Latest reported balance sheet", 1),
        ("Cash", "totalCash", "INR", "Latest reported balance sheet", 1),
        ("Operating cash flow", "operatingCashflow", "INR", "Trailing 12 months", 1),
        ("Free cash flow", "freeCashflow", "INR", "Trailing 12 months", 1),
        ("EPS", "trailingEps", "INR / share", "Trailing 12 months", 1),
    ]
    metrics = [dict(label=label, value=number(info.get(key), multiplier), unit=unit, period=period)
               for label, key, unit, period, multiplier in metric_fields]
    if info.get("financialCurrency") != "INR":
        for metric in metrics:
            if metric["unit"].startswith("INR") and metric["label"] != "Market capitalisation":
                metric["value"] = None
    notes = ["Personal-use, unofficial Yahoo Finance data; availability and reporting coverage can vary.",
             "Fetched time is not a financial reporting date. TTM means trailing 12 months; missing figures are unknown.",
             "Statement amounts are shown in their reported currency. Yahoo's reporting basis and periods may differ from Screener's consolidated figures.",
             "ROCE, promoter/FII/DII shareholding and annual-report footnotes are not supplied by this view. Use company filings and Screener to check them.",
             "This snapshot does not change your saved holdings, portfolio prices or document answers."]
    statements = []
    income_fields = [("Revenue", ["TotalRevenue"]), ("Operating profit", ["OperatingIncome"]),
                     ("Net income", ["NetIncome"]), ("Diluted EPS", ["DilutedEPS"])]
    table_specs = [
        (ticker.get_income_stmt, {"freq": "yearly"}, "Annual profit & loss", income_fields),
        (ticker.get_income_stmt, {"freq": "quarterly"}, "Quarterly profit & loss", income_fields),
        (ticker.get_balance_sheet, {}, "Annual balance sheet", [("Total assets", ["TotalAssets"]),
            ("Total debt", ["TotalDebt"]), ("Shareholders' equity", ["StockholdersEquity"])]),
        (ticker.get_cashflow, {}, "Annual cash flow", [("Operating cash flow", ["OperatingCashFlow"]),
            ("Capital expenditure", ["CapitalExpenditure"]), ("Free cash flow", ["FreeCashFlow"])])]
    statement_currency = info.get("financialCurrency")
    if statement_currency != "INR":
        notes.append("Statements were omitted because their reporting currency could not be verified as INR.")
    else:
        for method, kwargs, title, fields in table_specs:
            try:
                table = statement(method(**kwargs), title, statement_currency, fields)
            except Exception:
                table = None
            if table:
                statements.append(table)
            else:
                notes.append(f"{title} is unavailable from the provider.")
    price_as_of = None
    try:
        price_as_of = datetime.fromtimestamp(info["regularMarketTime"], tz=timezone.utc)
    except (KeyError, TypeError, ValueError, OSError, OverflowError):
        pass
    return dict(name=str(name)[:200], sector=info.get("sector"), industry=info.get("industry"), currency="INR",
                price=number(info.get("regularMarketPrice")), price_as_of=price_as_of,
                metrics=metrics, statements=statements, notes=notes)
