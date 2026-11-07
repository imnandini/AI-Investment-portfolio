from uuid import UUID
from app.analytics.portfolio import calculate_portfolio_analytics
from app.agents.portfolio_review.report import Finding, ReviewReport
from app.rag.retrieval import retrieve
from app.schemas.research import SearchRequest
from app.services.prices import require_portfolio, saved_prices
from app.agents.portfolio_review.verification import evidence_gaps


def build_nodes(session, settings):
    def calculate(state):
        portfolio = require_portfolio(session, UUID(state["user_id"]), UUID(state["portfolio_id"]))
        result = calculate_portfolio_analytics(portfolio, saved_prices(session, portfolio.id))
        targets = sorted(result.positions, key=lambda p: -p.cost_basis)[:5]
        return {"analytics": result.model_dump(mode="json"), "targets": [p.symbol for p in targets],
            "limitations": result.completeness_notes + ["Live market data and brokerage connections are disabled."],
            "activities": ["Verified portfolio ownership", "Calculated portfolio metrics", "Selected up to five research targets"]}

    def research(state):
        evidence = []
        gaps = list(state["limitations"])
        for symbol in state["targets"]:
            try:
                found = retrieve(session, UUID(state["user_id"]), SearchRequest(query="revenue profit risk debt liquidity", company=symbol, limit=2), settings)
            except Exception:
                found = []
                gaps.append(f"{symbol}: document retrieval is temporarily unavailable.")
            evidence.extend(item.model_dump(mode="json") for item in found)
            if not found:
                gaps.append(f"{symbol}: no matching document evidence for revenue, profit, debt or risks.")
        return {"evidence": evidence, "limitations": gaps, "activities": state["activities"] + ["Retrieved company evidence"]}

    def no_targets(state):
        return {"evidence": [], "activities": state["activities"] + ["Skipped research: no holdings"]}

    def verify(state):
        # Never reconcile conflicting values across periods by guessing. The report remains extractive.
        gaps = state["limitations"] + evidence_gaps(state.get("evidence", [])) + ["Uploaded excerpts are unverified and may contain conflicting claims. No cross-period financial comparison is inferred."]
        return {"limitations": gaps, "activities": state["activities"] + ["Checked evidence scope and citation metadata"]}

    def report(state):
        metrics = state["analytics"]
        findings = [Finding(title="Portfolio structure", basis="calculation",
            text=f"{len(metrics['positions'])} positions. Cost basis: {metrics['cost_basis_total'] or 'unavailable'} {metrics['base_currency']}. Asset and sector allocations use cost basis.")]
        if metrics["complete"]:
            findings.append(Finding(title="Market concentration", basis="calculation", text=f"Largest position: {metrics['largest_holding_symbol']} at {metrics['largest_holding_allocation_pct']}%. Concentration index: {metrics['concentration_index']} on a 0–10,000 scale."))
        else:
            findings.append(Finding(title="Incomplete valuation", basis="data_gap", text="Fresh matching prices in the base currency are required for complete market value and concentration metrics."))
        for i, item in enumerate(state.get("evidence", [])):
            findings.append(Finding(title=f"{item['company']} source excerpt", text=item["text"], basis="source_excerpt", evidence_indices=[i]))
        result = ReviewReport(summary="Portfolio structure and source excerpts for research follow-up.", analytics=metrics,
            findings=findings, evidence=state.get("evidence", []), limitations=list(dict.fromkeys(state["limitations"])),
            follow_up_questions=["Are the allocation and concentration consistent with your intended portfolio structure?", "Which holdings need fresh prices or more recent disclosure documents?"],
            activities=state["activities"] + ["Validated and saved report"])
        return {"report": result.model_dump(mode="json")}
    return calculate, research, no_targets, verify, report
