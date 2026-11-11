"""Portfolio questions answered from saved calculations and dated public news.

Routing is deterministic; source text is never interpreted as an instruction.
Documents supplement the answer and are not a prerequisite for portfolio checks.
"""
import re

from app.integrations.company_news import company_terms, utcnow
from app.rag.answering import grounded_answer
from app.services.research_briefs import holding_brief, portfolio_brief


def matches(pattern, question):
    return re.search(pattern, question, re.I) is not None


def named_holdings(question, holdings):
    """Use whole symbols/names, so e.g. IT does not match 'with'."""
    normalized = " ".join(re.findall(r"[a-z0-9]+", question.casefold()))
    found = []
    for holding in holdings:
        instrument = holding.instrument
        aliases = [instrument.canonical_symbol, instrument.display_name or ""]
        if instrument.display_name:
            aliases.append(" ".join(company_terms(instrument.display_name)))
        for alias in aliases:
            alias = " ".join(re.findall(r"[a-z0-9]+", alias.casefold()))
            if not alias:
                continue
            if len(alias) <= 2 and not re.search(r"(?<!\w)" + re.escape(alias.upper()) + r"(?!\w)", question):
                continue
            if re.search(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", normalized):
                found.append(holding)
                break
    return found


def news_section(brief):
    return {"name": brief["name"], "symbol": brief["symbol"], **brief["news"]}


def stock_text(brief):
    parts = [brief["name"] + ": " + brief["view"], brief["analysis"][1]["text"]]
    if brief["news"]["articles"]:
        parts.append("Recent headlines (see dated source links below):\n" + "\n".join(
            "- " + article["title"] for article in brief["news"]["articles"][:3]))
    else:
        parts.append(brief["news"]["note"] + " I cannot confirm what the company is doing currently from this feed.")
    return "\n\n".join(parts)


def metric_text(portfolio, metrics, selected, question):
    names = {(h.instrument.canonical_symbol, h.instrument.exchange): h.instrument.display_name or h.instrument.canonical_symbol
             for h in portfolio.holdings}
    keys = {(h.instrument.canonical_symbol, h.instrument.exchange) for h in selected}
    positions = [p for p in metrics.positions if not keys or (p.symbol, p.exchange) in keys]
    if not positions:
        return "No security holdings are saved in this portfolio. Import holdings or add a position in Portfolios to calculate allocation and performance."
    parts = []
    if not selected:
        def amount(value):
            return f"{value} {portfolio.base_currency}" if value is not None else "unavailable with the saved inputs"
        parts.append(f"{portfolio.name} has {len(positions)} security positions.\nRecorded cost basis: {amount(metrics.cost_basis_total)}.\n"
                     f"Market value: {amount(metrics.market_value_total)}.\nUnrealized gain/loss: {amount(metrics.unrealized_pl_total)}.")
    parts.append("Saved holdings (up to 20 shown):")
    for p in positions[:20]:
        line = f"- {names[(p.symbol, p.exchange)]}: {p.quantity.normalize():f} units; cost basis {str(p.cost_basis) if p.cost_basis is not None else 'unknown'} {p.currency}"
        weight = p.market_allocation_pct if metrics.complete else p.cost_basis_allocation_pct
        if weight is not None:
            line += f"; {weight}% of security {'market value' if metrics.complete else 'cost basis'}"
        if p.price_status == "available":
            line += f"; saved market value {p.market_value} {p.currency} (price as of {p.price_as_of.isoformat()})"
            if p.unrealized_pl is not None:
                line += f"; unrealized gain/loss {p.unrealized_pl} {p.currency}"
            if p.unrealized_return_pct is not None:
                line += f"; unrealized return {p.unrealized_return_pct}% on average purchase cost"
        else:
            line += f"; usable current price unavailable ({p.price_status})"
        parts.append(line + ".")
    if matches(r"\b(sector|allocation|mix)\b", question):
        parts.append("Sector mix by known base-currency purchase cost:")
        for sector in metrics.sector_mix:
            allocation = f"{sector.allocation_pct}%" if sector.allocation_pct is not None else "complete percentage unavailable"
            parts.append(f"- {sector.name}: {sector.cost_basis} {portfolio.base_currency}; {allocation}.")
    parts.append("These are saved-position calculations, not a live quote. Unrealized return percentages are cumulative price changes on current holdings, not annualized returns; they exclude realized trades, dividends, fees and taxes.")
    return "\n".join(parts)


async def answer_question(session, settings, user_id, portfolio, metrics, question, evidence):
    selected = named_holdings(question, portfolio.holdings)
    response = {"status": "supported", "method": "portfolio-chat-v1", "answer": "",
                "evidence": [item.model_dump(mode="json") for item in evidence], "news": [],
                "limitations": list(metrics.completeness_notes),
                "activities": ["Loaded your portfolio and calculated saved-position metrics"],
                "generated_at": utcnow().isoformat()}
    document_question = matches(r"\b(document|documents|pdf|report|reports|uploaded|filing|filings|passage|passages)\b", question)
    news_question = matches(r"\b(news|latest|currently|recent|happening|happened|doing|updates?|developments?)\b", question)
    metric_question = matches(r"\b(prices?|value|worth|invested|investment amount|cost basis|profit|loss|gains?|returns?|performance|performing|allocation|sector|sectors|weights?|holdings|positions|quantity|quantities)\b", question)
    overview_question = matches(r"\b(portfolio|overall|diversif\w*|concentration|concentrated|risks?|risky|health|healthy|okay|ok|good|review|safe|balanced|balance)\b", question)

    if document_question and not matches(r"\bnews\b", question):
        response.update(grounded_answer(evidence).model_dump(mode="json"))
    elif matches(r"\b(what is|what does|explain|define)\b", question) and not selected and matches(r"\b(diversification|cost basis|unrealized|concentration)\b", question):
        if matches(r"\bdiversification\b", question):
            response["answer"] = "Diversification spreads exposure across companies, sectors and asset types so one event has less influence on your whole portfolio. Several stock names can still share the same industry risks. Ask 'Is my portfolio diversified?' to check your saved positions."
        elif matches(r"\bcost basis\b", question):
            response["answer"] = "Recorded cost basis is quantity multiplied by average purchase cost. Cost-basis weights show where purchase capital was assigned; current market weights can differ as prices change. Missing purchase costs remain unknown."
        elif matches(r"\bunrealized\b", question):
            response["answer"] = "Unrealized gain or loss is the value of shares you still hold minus their recorded purchase cost. It changes with prices and excludes realized trades, dividends, fees and taxes in this app."
        else:
            response["answer"] = "Concentration means a large part of your portfolio depends on a company, sector or shared business driver. A large holding can strongly influence results. Ask 'Is my portfolio concentrated?' to check security weights using your saved prices or purchase costs."
    elif metric_question and not news_question:
        response["answer"] = metric_text(portfolio, metrics, selected, question)
    elif news_question and not selected and not (
        matches(r"\b(my|portfolio|companies|holdings|stocks)\b", question)
        or re.fullmatch(r"\s*(?:what(?:'s| is) (?:the )?)?(?:latest |recent |company )?(?:news|updates)[?! .]*", question, re.I)
    ):
        response["status"] = "insufficient_evidence"
        names = [h.instrument.display_name or h.instrument.canonical_symbol for h in portfolio.holdings]
        response["answer"] = "I could not match a saved company to this question. Include its full saved name or symbol so I check the right company."
        if names:
            response["answer"] += " Your saved holdings include: " + ", ".join(names[:10]) + "."
    elif selected or news_question or overview_question:
        if selected:
            stocks = []
            for holding in selected[:3]:
                if holding.instrument.asset_type.upper() not in ("EQUITY", "STOCK"):
                    response["limitations"].append(f"Company news is available for equities; {holding.instrument.display_name or holding.instrument.canonical_symbol} is a fund or another asset type.")
                    continue
                stocks.append(await holding_brief(session, settings, user_id, portfolio.id, holding.id))
            response["answer"] = "\n\n".join(stock_text(stock) for stock in stocks) if stocks else metric_text(portfolio, metrics, selected, question)
            for stock in stocks:
                response["news"].append(news_section(stock))
                response["limitations"].extend(stock["limitations"])
            if len(selected) > 3:
                response["limitations"].append("This answer checks up to three named holdings. Ask about the others individually.")
        else:
            # The existing brief bounds public I/O to ten equities and never sends
            # the user's question, quantities or private account labels to news.
            brief = await portfolio_brief(session, settings, user_id, portfolio.id)
            parts = [brief["view"]]
            if brief["strengths"]:
                parts.append("What looks supported:\n" + "\n".join("- " + item for item in brief["strengths"]))
            if brief["concerns"]:
                parts.append("What deserves a closer look:\n" + "\n".join("- " + item for item in brief["concerns"]))
            if news_question:
                parts.extend(stock_text(stock) for stock in brief["stocks"])
                if not brief["stocks"]:
                    parts.append("No saved equity holdings are available for a company-news check. Add your company holdings in Portfolios first.")
            elif brief["stocks"]:
                parts.append("Recent company news is linked below. Ask about a company by its saved name or symbol for more detail.")
            parts.append("I can assess the saved holdings and data gaps, but whether the overall portfolio fits you also depends on your goals, time horizon, income needs and other assets.")
            response["answer"] = "\n\n".join(parts)
            response["news"] = [news_section(stock) for stock in brief["stocks"]]
            response["limitations"].extend(brief["limitations"])
            response["limitations"].extend(stock["news"]["note"] for stock in brief["stocks"])
        response["activities"].append("Checked recent public news for saved equity holdings")
    elif evidence:
        response.update(grounded_answer(evidence).model_dump(mode="json"))
    else:
        response["status"] = "insufficient_evidence"
        response["answer"] = ("I can check your portfolio's concentration, diversification, allocation and saved gain/loss, or look up recent news for companies you hold. "
                              "Try 'Is my overall portfolio okay?', 'How much is my portfolio worth?' or 'What are my companies doing currently?' "
                              "For a specific company, include its saved name or symbol. A precise business figure needs a dated source; I could not establish it from the available evidence.")
    response["limitations"] = list(dict.fromkeys(response["limitations"]))
    return response
