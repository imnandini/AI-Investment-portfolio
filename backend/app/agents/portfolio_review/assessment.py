"""Specific, calculation-backed review findings and attributed headline signals."""
from decimal import Decimal

from app.agents.portfolio_review.report import Finding
from app.services.research_briefs import news_signals, POSITIVE, NEGATIVE

NEWS_LIMIT = 20
SELECTION_POLICY = "All saved positions are calculated. News checks prioritize up to 20 listed stock/ETF holdings by fresh base-currency market value when complete, otherwise by known recorded cost in the base currency. Unknown or foreign-currency values sort last. Remaining holdings are not news-checked in this review."


def number(value):
    return Decimal(str(value)) if value is not None else None


def weight(holding, metrics):
    return number(holding["market_allocation_pct"] if metrics["complete"] else holding["cost_basis_allocation_pct"])


def company_assessment(holding, news, metrics):
    basis = "market value" if metrics["complete"] else "recorded cost basis"
    allocation = weight(holding, metrics)
    positives = news_signals(news["articles"], POSITIVE) if not holding["is_fund"] else []
    concerns = news_signals(news["articles"], NEGATIVE) if not holding["is_fund"] else []
    if holding["is_fund"]:
        view = f"{holding['name']} is a fund/ETF holding. Matched news is fund-level coverage; company earnings rules are not applied to the fund. Its underlying constituents and their overlap with your direct stocks have not been established."
    elif positives or concerns:
        topics = "; ".join(item["title"] for item in positives + concerns)
        view = f"Recent headlines for {holding['name']} flag these research topics: {topics}. The linked headlines support these topic signals; they do not establish their financial magnitude or the stock's valuation."
    elif news["articles"]:
        latest = news["articles"][0]
        view = f"{len(news['articles'])} recent matched headlines were found for {holding['name']}. The latest is \"{latest['title']}\" from {latest['publisher']}. The topic rules did not identify a supported positive or concern signal; the source links remain available for inspection."
    else:
        view = f"Recent developments for {holding['name']} could not be established from the available news feed. {news['note']} Its calculated portfolio exposure remains available below."
    if allocation is None:
        impact = "A complete portfolio weight is unavailable. Missing prices, purchase costs or FX prevent a reliable exposure percentage."
    elif metrics["complete"]:
        sensitivity = (allocation / Decimal(10)).quantize(Decimal("0.01"))
        impact = f"This holding is {allocation}% of security market value. A 10% price move in this holding alone would move the current security basket by about {sensitivity}%, assuming other prices and quantities stay unchanged."
    else:
        impact = f"This holding is {allocation}% of recorded security cost basis. This describes purchase capital, not today's market weight; current price sensitivity cannot be inferred from this measure."
    return {"name": holding["name"], "symbol": holding["symbol"], "exchange": holding["exchange"],
            "is_fund": holding["is_fund"], "weight_pct": allocation, "weight_basis": basis,
            "unrealized_return_pct": holding.get("unrealized_return_pct"), "price_as_of": holding.get("price_as_of"),
            "view": view, "portfolio_impact": impact, "positive_signals": positives,
            "concern_signals": concerns, "news": news}


def build_assessment(state):
    metrics, holdings, coverage = state["analytics"], state["holdings"], state["coverage"]
    basis = coverage["weight_basis"]
    currency = metrics["base_currency"]
    def money(value):
        return f"{value} {currency}" if value is not None else "unavailable"
    snapshot = (f"{len(holdings)} saved security positions. Recorded purchase cost: {money(metrics['cost_basis_total'])}. "
                f"Latest usable market value: {money(metrics['market_value_total'])}. Unrealized gain/loss: {money(metrics['unrealized_pl_total'])}.")
    if metrics.get("unrealized_return_pct") is not None:
        snapshot += f" The cumulative unrealized price return is {metrics['unrealized_return_pct']}% on recorded cost; dividends, realized trades, fees and taxes are excluded."
    findings = [Finding(title="Your portfolio in numbers", basis="calculation", text=snapshot)]
    known = [(holding, weight(holding, metrics)) for holding in holdings if weight(holding, metrics) is not None]
    largest = max(known, key=lambda pair: pair[1]) if known else None
    if largest:
        holding, allocation = largest
        label = "fund/ETF" if holding["is_fund"] else "company"
        text = f"{holding['name']} is the largest holding at {allocation}% of security {basis}. "
        if metrics["complete"]:
            sensitivity = (allocation / Decimal(10)).quantize(Decimal("0.01"))
            text += f"A 10% fall in this holding alone would reduce the current security basket by approximately {sensitivity}%, with all other prices and quantities unchanged. "
        else:
            text += "Cost weights identify where purchase capital was assigned; a complete fresh valuation is needed to measure current market sensitivity. "
        if allocation > Decimal(25):
            text += f"This makes the {label}'s outcome influential. The 25% level is a research review prompt, not a prescribed allocation limit."
        if len(known) > 3:
            top_three = sum((w for _, w in sorted(known, key=lambda item: -item[1])[:3]), Decimal(0))
            text += f" The three largest holdings together account for {top_three}% on this measure."
        findings.append(Finding(title="What drives your portfolio's risk", basis="calculation", text=text))
    elif holdings:
        findings.append(Finding(title="Exposure cannot yet be quantified", basis="data_gap", text="No complete market or cost allocation is available. This prevents a supported concentration assessment; unknown costs and prices have not been replaced with estimates."))
    missing = sum(not h.get("sector") for h in holdings)
    funds = [h["name"] for h in holdings if h["is_fund"]]
    if missing:
        diversification = f"Sector information is missing for {missing} of {len(holdings)} positions. Several names alone do not establish independent sector exposure."
    else:
        sectors = sorted(metrics["sector_mix"], key=lambda item: -(number(item["allocation_pct"]) or 0))
        diversification = "; ".join(f"{item['name']}: {item['allocation_pct']}% of known base-currency purchase cost" if item["allocation_pct"] is not None else f"{item['name']}: percentage unavailable with the saved purchase costs" for item in sectors[:3]) or "No sector allocation can be established from the saved inputs."
        if any(item["name"] != "Unknown" and item["allocation_pct"] is not None and number(item["allocation_pct"]) > 40 for item in sectors):
            diversification += ". A known sector exceeds the 40% research review prompt, so apparently different companies may share an important industry driver. This threshold is not a prescribed limit."
    if funds:
        diversification += " Fund/ETF holdings include " + ", ".join(funds[:3]) + ". Their underlying holdings and overlap are not available, so this review does not treat them as single operating companies or assume they diversify the direct stocks."
    findings.append(Finding(title="How much diversification is established?", basis="data_gap" if missing or funds else "calculation", text=diversification))
    valued = [h for h in holdings if h["currency"] == currency and h["price_status"] == "available" and h["unrealized_pl"] is not None]
    contributions = []
    gains = [h for h in valued if number(h["unrealized_pl"]) > 0]
    losses = [h for h in valued if number(h["unrealized_pl"]) < 0]
    for holding in ([max(gains, key=lambda h: number(h["unrealized_pl"]))] if gains else []) + ([min(losses, key=lambda h: number(h["unrealized_pl"]))] if losses else []):
        amount = holding["unrealized_pl"]
        contributions.append(f"{holding['name']}: {amount} {currency} unrealized gain/loss" + (f" ({holding['unrealized_return_pct']}%)" if holding.get("unrealized_return_pct") is not None else "") + f", using the price dated {holding['price_as_of'][:10]}.")
    if contributions:
        findings.append(Finding(title="The largest current gain/loss contributors", basis="calculation", text=" ".join(contributions) + " These are current-position price returns, not forecasts or annualized performance."))
    companies = state.get("company_reviews", [])
    focus = [company for company in companies if company["concern_signals"]] + [company for company in companies if company["positive_signals"] and not company["concern_signals"]]
    for company in focus[:3]:
        for signal in company["concern_signals"][:1] + company["positive_signals"][:1]:
            findings.append(Finding(title=f"{company['name']}: {signal['title']}", basis="headline_signal",
                text=signal["explanation"] + " " + company["portfolio_impact"] + " Next check: " + signal["text"], source_ids=signal["source_ids"]))
    if largest and largest[1] > Decimal(25):
        summary = f"{state['portfolio_name']}: concentration deserves attention. {largest[0]['name']} accounts for {largest[1]}% of security {basis}."
    elif not missing and any(item["name"] != "Unknown" and item["allocation_pct"] is not None and number(item["allocation_pct"]) > 40 for item in metrics["sector_mix"]):
        sector = max((item for item in metrics["sector_mix"] if item["name"] != "Unknown" and item["allocation_pct"] is not None), key=lambda item: number(item["allocation_pct"]))
        summary = f"{state['portfolio_name']}: sector exposure deserves attention. {sector['name']} accounts for {sector['allocation_pct']}% of security purchase cost."
    elif not metrics["complete"]:
        summary = f"{state['portfolio_name']}: the current portfolio assessment is limited by incomplete valuation data."
    else:
        summary = f"{state['portfolio_name']}: no single holding exceeds the 25% review prompt; sector overlap and the company evidence still need to be considered."
    if not holdings:
        summary = "No saved holdings are available for a portfolio assessment."
    questions = []
    if largest:
        questions.append(f"How much exposure to {largest[0]['name']} did you intend, compared with its current {largest[1]}% of {basis}?")
    flagged = [company for company in state.get("company_reviews", []) if company["concern_signals"]]
    questions.extend(f"For {company['name']}: {company['concern_signals'][0]['text']}" for company in flagged[:3])
    if missing:
        questions.append(f"Which sectors and business drivers sit behind the {missing} holdings with missing sector information?")
    if funds:
        questions.append(f"What are the underlying exposures of {funds[0]}, and do they overlap with your other investments?")
    if not metrics["complete"]:
        questions.append("Which missing, stale or currency-mismatched prices prevent a complete current valuation?")
    if coverage["unreviewed_positions"]:
        questions.append(f"Which of the {coverage['unreviewed_positions']} listed holdings outside this news sample should be researched next?")
    return summary, findings, questions
