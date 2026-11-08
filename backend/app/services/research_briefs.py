"""Source-linked research signals and calculation-based portfolio observations.

No model key is needed. Headline rules identify topics to investigate, never
verify business facts or produce price targets or personalized trade instructions.
"""
import asyncio
from decimal import Decimal
import re

from fastapi import HTTPException

from app.analytics.portfolio import calculate_portfolio_analytics
from app.integrations.company_news import company_news, utcnow
from app.rag.retrieval import retrieve
from app.schemas.research import SearchRequest
from app.services.indmoney import list_balances
from app.services.prices import require_portfolio, saved_prices

POSITIVE = [
    ("Earnings growth reported", r"\b(?:profit|earnings|revenue|sales)\b.{0,25}\b(?:rise[sn]?|rising|rose|grew|growth|surge[sd]?|jump[sd]?|increase[sd]?|up)\b", "Check whether growth also appears in margins, operating cash flow and the latest company filing."),
    ("New business reported", r"\b(?:wins?|bags?|secures?|awarded)\b.{0,35}\b(?:orders?|contracts?|deals?)\b", "Check contract size, execution timing and how much revenue the order could contribute."),
    ("Debt reduction reported", r"\b(?:cuts?|reduces?|repaid|repays?)\b.{0,15}\bdebt\b|\bdebt\b.{0,15}\b(?:falls?|declines?|reductions?|free)\b", "Check net debt, cash balances and whether the improvement is recurring."),
]
NEGATIVE = [
    ("Earnings pressure reported", r"\b(?:profit|earnings|revenue|sales|margins?)\b.{0,25}\b(?:falls?|fell|drops?|declines?|declined|slumps?|down|shrinks?)\b|\b(?:loss|losses)\b.{0,15}\b(?:widens?|widened|surges?|rises?)\b", "Check whether the weakness comes from recurring operations, one-off charges or changes in demand."),
    ("Regulatory or governance concern reported", r"\b(?:probe|investigation|fraud|penalty|penalties|fined|lawsuit|auditor resigns|regulatory action)\b", "Check the company or regulator's disclosure for scope, materiality and the company's response."),
    ("Financial stress reported", r"\b(?:default|defaults|bankruptcy|insolvency|debt crisis|credit downgrade)\b", "Check repayment obligations, liquidity and the latest credit or exchange disclosures."),
]


def news_signals(articles, rules):
    signals = []
    for title, pattern, follow_up in rules:
        matches = []
        for article in articles:
            headline = article["title"].casefold()
            # Denials, hypothetical and negated claims stay in the neutral news list.
            if re.search(r"\b(?:not|no|denies?|denied|avoids?|without|may|might|could|rumou?r|alleged)\b", headline):
                continue
            if re.search(pattern, headline):
                matches.append(article["id"])
        if matches:
            signals.append({"title": title, "text": follow_up, "source_ids": matches, "basis": "headline_signal"})
    return signals


def document_evidence(session, settings, user_id, symbol):
    try:
        found = retrieve(session, user_id, SearchRequest(query="revenue profit cash flow debt risks growth", company=symbol, limit=3), settings)
        return [item.model_dump(mode="json") for item in found], None
    except Exception:
        return [], "Your document library could not be searched for this brief."


def stock_brief(holding, news, evidence, doc_issue, metrics):
    instrument = holding.instrument
    name = instrument.display_name or instrument.canonical_symbol
    pros = news_signals(news["articles"], POSITIVE)
    cons = news_signals(news["articles"], NEGATIVE)
    if pros and cons:
        view = "Mixed news signals. Recent coverage includes both potential positives and concerns; compare the cited reports with company filings before forming a stock view."
    elif pros:
        view = "Potential positives appear in recent coverage. The evidence is too narrow to judge valuation or establish that the stock is attractive at its current price."
    elif cons:
        view = "Recent coverage flags issues worth investigating. Check their financial impact and the company's response before drawing a conclusion about the stock."
    else:
        view = "There is not enough directional evidence for a supported stock opinion. Read the matched news and company disclosures; an absence of flagged concerns does not establish safety."
    key = (instrument.canonical_symbol, instrument.exchange)
    position = next((p for p in metrics.positions if (p.symbol, p.exchange) == key), None)
    limitations = [news["note"], "Pros and cons are conservative topic signals from headlines, not a full-article analysis, analyst consensus or an independently verified investment thesis.",
                  "Fundamentals, valuation and your investment goals have not been assessed. No buy/sell rating or price target is generated."]
    if not evidence:
        limitations.append("No matching uploaded company documents were found for this brief.")
    if doc_issue:
        limitations.append(doc_issue)
    if position and position.price_status != "available":
        limitations.append("This holding has no fresh, dated price usable in aggregate market metrics.")
    return {"kind": "stock", "holding_id": str(holding.id), "name": name, "symbol": instrument.canonical_symbol,
            "generated_at": utcnow().isoformat(), "view": view, "pros": pros, "cons": cons,
            "news": news, "evidence": evidence, "limitations": limitations,
            "portfolio_context": {"cost_weight_pct": str(position.cost_basis_allocation_pct) if position and position.cost_basis_allocation_pct is not None else None,
                                  "market_weight_pct": str(position.market_allocation_pct) if position and position.market_allocation_pct is not None else None},
            "questions": ["Are earnings backed by recurring cash flow?", "How do debt, valuation and growth compare with the company's history and peers?", "Which recent events materially change the original investment thesis?"]}


async def holding_brief(session, settings, user_id, portfolio_id, holding_id):
    portfolio = require_portfolio(session, user_id, portfolio_id)
    holding = next((h for h in portfolio.holdings if h.id == holding_id), None)
    if holding is None:
        raise HTTPException(404, "Holding not found in this portfolio.")
    if holding.instrument.asset_type.upper() not in ("EQUITY", "STOCK"):
        raise HTTPException(422, "Stock briefs are available for equity holdings. Use document research for funds and PF accounts.")
    metrics = calculate_portfolio_analytics(portfolio, saved_prices(session, portfolio_id))
    evidence, doc_issue = document_evidence(session, settings, user_id, holding.instrument.canonical_symbol)
    news = await company_news(holding.instrument.display_name or holding.instrument.canonical_symbol, holding.instrument.currency)
    return stock_brief(holding, news, evidence, doc_issue, metrics)


async def portfolio_brief(session, settings, user_id, portfolio_id):
    portfolio = require_portfolio(session, user_id, portfolio_id)
    metrics = calculate_portfolio_analytics(portfolio, saved_prices(session, portfolio_id))
    names = {h.instrument.canonical_symbol: h.instrument.display_name or h.instrument.canonical_symbol for h in portfolio.holdings}
    balances = list_balances(session, user_id, portfolio_id)
    strengths, concerns = [], []
    if not portfolio.holdings:
        concerns.append("No security holdings are saved. Import the reviewed holdings to assess this portfolio.")
    weights = [(p, p.market_allocation_pct if metrics.complete else p.cost_basis_allocation_pct) for p in metrics.positions]
    basis = "market value" if metrics.complete else "cost basis"
    known = [(p, w) for p, w in weights if w is not None]
    if known:
        largest, weight = max(known, key=lambda pair: pair[1])
        label = names[largest.symbol]
        if weight > Decimal(25):
            concerns.append(f"{label} represents {weight}% of security {basis}. Results are sensitive to this single holding.")
        else:
            strengths.append(f"The largest security is {label} at {weight}% of {basis}; no single security exceeds 25% on this measure.")
    if 0 < len(metrics.positions) < 5:
        concerns.append(f"There are only {len(metrics.positions)} security positions. A small number of names can leave substantial company-specific exposure.")
    if metrics.complete:
        strengths.append("Every security has a fresh, currency-matched price, so market weights and concentration can be calculated.")
    elif metrics.positions:
        concerns.append(f"Only {metrics.priced_position_count} of {len(metrics.positions)} securities have fresh usable prices. Current market allocation cannot be fully assessed.")
    missing_sector = sum(not h.instrument.sector for h in portfolio.holdings)
    if missing_sector:
        concerns.append(f"Sector information is missing for {missing_sector} securities, so sector diversification is unverified.")
    elif metrics.sector_mix:
        for sector in metrics.sector_mix:
            if sector.allocation_pct is not None and sector.allocation_pct > Decimal(40):
                concerns.append(f"{sector.name} accounts for {sector.allocation_pct}% of security cost basis. Check correlated industry risks.")
    # Snapshot ORM/doc data before parallel I/O; the SQLAlchemy session is never
    # used concurrently. Only public company-name queries run in parallel.
    targets = sorted((h for h in portfolio.holdings if h.instrument.asset_type.upper() in ("EQUITY", "STOCK")),
        key=lambda h: -(h.quantity * h.average_cost if h.average_cost is not None else Decimal(0)))[:10]
    docs = [document_evidence(session, settings, user_id, h.instrument.canonical_symbol) for h in targets]
    semaphore = asyncio.Semaphore(3)

    async def fetch(holding):
        async with semaphore:
            return await company_news(holding.instrument.display_name or holding.instrument.canonical_symbol, holding.instrument.currency)

    news_results = await asyncio.gather(*(fetch(h) for h in targets))
    stocks = [stock_brief(h, news, evidence, issue, metrics) for h, news, (evidence, issue) in zip(targets, news_results, docs)]
    flagged = [brief["name"] for brief in stocks if brief["cons"]]
    if flagged:
        concerns.append("Recent news contains concern signals for " + ", ".join(flagged[:5]) + ". See the source-linked stock briefs below.")
    if known and max(weight for _, weight in known) > Decimal(25):
        view = "Concentration deserves attention. A large share sits in one security, so that company's results can strongly influence this portfolio."
    elif not metrics.complete:
        view = "The portfolio view is incomplete. Fresh prices and sector information are needed to judge current concentration and diversification."
    else:
        view = "No single security exceeds the 25% review threshold, but that alone does not establish diversification or suitability. Review sector overlap and the company news below."
    limitations = list(metrics.completeness_notes) + ["This is a rules-based research view, not a personalized suitability assessment. The 25% single-name and 40% sector thresholds are review prompts, not prescribed allocation limits.",
        f"News checks cover up to 10 equity holdings ranked by recorded cost basis; {len(targets)} checked. Missing costs sort last. Names and headlines may be ambiguous; full articles are not automatically verified.",
        "Investment goals, horizon, income needs, tax position and other assets are unknown. A buy/sell decision cannot be inferred from this brief."]
    if balances:
        limitations.append(f"{len(balances)} PF account balances are displayed separately and excluded from these security weights. This is not a complete household net-worth allocation.")
    return {"kind": "portfolio", "name": portfolio.name, "generated_at": utcnow().isoformat(), "view": view,
            "strengths": strengths, "concerns": concerns, "stocks": stocks, "limitations": limitations,
            "weight_basis": basis, "security_count": len(metrics.positions), "pf_account_count": len(balances),
            "questions": ["Does the largest holding's weight fit the amount of company-specific risk you intended?", "Do holdings overlap in sector, business drivers or geography?", "Are PF, cash and other investments part of your intended overall allocation?"]}
