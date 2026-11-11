import asyncio
from decimal import Decimal
import re
from uuid import UUID

from app.analytics.portfolio import calculate_portfolio_analytics
from app.agents.portfolio_review.assessment import NEWS_LIMIT, SELECTION_POLICY, build_assessment, company_assessment, number
from app.agents.portfolio_review.report import Finding, NewsSource, ReviewReport
from app.agents.portfolio_review.verification import evidence_gaps
from app.integrations.company_news import company_news, public_link, utcnow
from app.rag.retrieval import retrieve
from app.schemas.research import SearchRequest
from app.services.daily_prices import ensure_daily_prices
from app.services.indmoney import list_balances
from app.services.prices import require_portfolio, saved_prices


def eligible(holding):
    return holding['asset_type'].upper() in ('EQUITY', 'STOCK', 'ETF')


def normalize_news(result, index):
    articles = []
    seen = set()
    for item in result.get('articles', [])[:8]:
        link = public_link(item.get('url'))
        if not link or link in seen:
            continue
        try:
            article = NewsSource.model_validate({**item, 'id': f'company-{index + 1}-news-{len(articles) + 1}', 'url': link})
        except Exception:
            continue
        if article.published_at.utcoffset() is None:
            continue
        seen.add(link)
        articles.append(article.model_dump(mode='json'))
    status = 'available' if articles else result.get('status', 'unavailable')
    if status == 'available':
        status = 'empty' if not articles else 'available'
    return {'status': status, 'articles': articles, 'checked_at': result.get('checked_at'),
            'provider': result.get('provider'), 'cached': result.get('cached', False),
            'note': result.get('note', 'Recent company news could not be established.')}


def build_nodes(session, settings):
    async def calculate(state):
        portfolio = require_portfolio(session, UUID(state['user_id']), UUID(state['portfolio_id']))
        await ensure_daily_prices(session, portfolio, settings)
        result = calculate_portfolio_analytics(portfolio, saved_prices(session, portfolio.id))
        metrics = result.model_dump(mode='json')
        positions = {(p['symbol'], p['exchange']): p for p in metrics['positions']}
        holdings = []
        for holding in portfolio.holdings:
            instrument = holding.instrument
            name = instrument.display_name or instrument.canonical_symbol
            holdings.append({**positions[(instrument.canonical_symbol, instrument.exchange)],
                             'holding_id': str(holding.id), 'name': name,
                             'is_fund': instrument.asset_type.upper() in ('ETF', 'MF', 'MUTUAL_FUND', 'MUTUAL FUND') or bool(re.search(r'\bETF\b', name, re.I))})
        def rank(holding):
            value = number(holding['market_value'] if metrics['complete'] else holding['cost_basis']) if holding['currency'] == metrics['base_currency'] else None
            return value is None, -(value or Decimal(0)), holding['name'], holding['exchange']
        targets = sorted((holding for holding in holdings if eligible(holding)), key=rank)[:NEWS_LIMIT]
        balances = list_balances(session, UUID(state['user_id']), portfolio.id)
        limitations = list(result.completeness_notes)
        if balances:
            limitations.append(f'{len(balances)} PF balances are separate from security weights and company-news checks; this is not a complete household asset allocation.')
        return {'portfolio_name': portfolio.name, 'analytics': metrics, 'holdings': holdings, 'targets': targets,
                'pf_account_count': len(balances), 'limitations': limitations,
                'activities': ['Verified portfolio ownership', 'Refreshed available daily prices and calculated all saved positions',
                               f'Selected {len(targets)} listed holdings for automatic news checks (maximum {NEWS_LIMIT})']}

    async def research(state):
        evidence, gaps = [], list(state['limitations'])
        # The database session is used sequentially before concurrent public I/O.
        for holding in state['targets']:
            try:
                found = retrieve(session, UUID(state['user_id']), SearchRequest(query='revenue profit risk debt liquidity', company=holding['symbol'], limit=2), settings)
                evidence.extend(item.model_dump(mode='json') for item in found)
            except Exception:
                gaps.append('Optional uploaded sources could not be searched for every selected holding. Calculations and news remain available.')
        semaphore = asyncio.Semaphore(4)
        async def fetch(index, holding):
            async with semaphore:
                try:
                    data = await company_news(holding['name'], holding['currency'])
                    return normalize_news(data, index)
                except Exception:
                    return {'status': 'unavailable', 'articles': [], 'checked_at': utcnow().isoformat(),
                            'note': 'The news feed could not be reached. No company developments have been inferred.'}
        tasks = {asyncio.create_task(fetch(index, holding)): index for index, holding in enumerate(state['targets'])}
        done, pending = await asyncio.wait(tasks, timeout=25)
        results = {tasks[task]: task.result() for task in done}
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        companies = []
        for index, holding in enumerate(state['targets']):
            news = results.get(index, {'status': 'not_checked', 'articles': [], 'checked_at': None,
                                      'note': 'This source check did not finish within the review time budget. Use the holding news brief to check it separately.'})
            companies.append(company_assessment(holding, news, state['analytics']))
        return {'evidence': evidence, 'company_reviews': companies, 'limitations': gaps,
                'activities': state['activities'] + ['Checked recent public company/fund news with bounded parallel requests', 'Searched optional uploaded documents']}

    def no_targets(state):
        return {'evidence': [], 'company_reviews': [], 'activities': state['activities'] + ['Skipped research: no holdings' if not state['holdings'] else 'No listed stock/ETF targets; retained portfolio calculations']}

    def verify(state):
        companies = state.get('company_reviews', [])
        checked = [company for company in companies if company['news']['status'] != 'not_checked']
        with_news = [company for company in checked if company['news']['articles']]
        eligible_count = sum(eligible(holding) for holding in state['holdings'])
        value_field = 'market_value' if state['analytics']['complete'] else 'cost_basis'
        total = number(state['analytics']['market_value_total'] if state['analytics']['complete'] else state['analytics']['cost_basis_total'])
        checked_keys = {(company['symbol'], company['exchange']) for company in checked}
        covered_value = sum((number(holding[value_field]) or Decimal(0) for holding in state['holdings']
                             if (holding['symbol'], holding['exchange']) in checked_keys and holding['currency'] == state['analytics']['base_currency']), Decimal(0))
        covered_weight = (covered_value / total * 100).quantize(Decimal('0.01')) if total is not None and total > 0 else None
        coverage = {'total_positions': len(state['holdings']), 'eligible_positions': eligible_count,
                    'selected_positions': len(state['targets']), 'checked_positions': len(checked),
                    'positions_with_news': len(with_news), 'positions_without_news': len(checked) - len(with_news),
                    'unreviewed_positions': eligible_count - len(checked), 'excluded_positions': len(state['holdings']) - eligible_count,
                    'checked_weight_pct': covered_weight, 'weight_basis': 'market value' if state['analytics']['complete'] else 'recorded cost basis',
                    'article_count': len({article['url'] for company in companies for article in company['news']['articles']}),
                    'selection_policy': SELECTION_POLICY}
        gaps = list(state['limitations'])
        if coverage['unreviewed_positions']:
            gaps.append(f"News was not checked for {coverage['unreviewed_positions']} listed holdings outside the completed sample. Their absence from concerns is not a positive assessment.")
        if coverage['positions_without_news']:
            gaps.append(f"{coverage['positions_without_news']} checked holdings had no usable recent matched headlines. See their source-check details below.")
        if coverage['excluded_positions']:
            gaps.append(f"{coverage['excluded_positions']} non-listed-stock/ETF positions are included in calculations where possible but excluded from company-news checks.")
        gaps.extend(evidence_gaps(state.get('evidence', [])))
        if state.get('evidence'):
            gaps.append('Optional uploaded excerpts are unverified and may refer to different periods or contain conflicting figures; no reconciliation is inferred.')
        gaps.extend(['News views identify topics from company-matched headlines, not verified full-article analysis, fundamentals or valuation.',
                     'Goals, time horizon and other assets are not established. The review is research context, not a personalized suitability or buy/sell recommendation.'])
        return {'coverage': coverage, 'limitations': list(dict.fromkeys(gaps)),
                'activities': state['activities'] + ['Checked source links, coverage and optional document citations']}

    def report(state):
        summary, findings, questions = build_assessment(state)
        names = {holding['symbol']: holding['name'] for holding in state['holdings']}
        for index, item in enumerate(state.get('evidence', [])):
            findings.append(Finding(title=f"{names.get(item['company'], item['company'])}: optional source excerpt", text=item['text'], basis='source_excerpt', evidence_indices=[index]))
        coverage = state['coverage']
        material_gaps = (not state['analytics']['complete'] or state['analytics']['cost_basis_total'] is None
                         or any(not holding.get('sector') or holding['is_fund'] for holding in state['holdings'])
                         or coverage['unreviewed_positions'] > 0 or coverage['positions_without_news'] > 0 or coverage['excluded_positions'] > 0)
        result = ReviewReport(summary=summary, assessment_status='partial' if material_gaps else 'complete', generated_at=utcnow(),
            analytics=state['analytics'], findings=findings, evidence=state.get('evidence', []), company_reviews=state.get('company_reviews', []),
            coverage=coverage, limitations=state['limitations'], follow_up_questions=questions,
            activities=state['activities'] + ['Validated and saved the calculation and news snapshot'])
        return {'report': result.model_dump(mode='json')}
    return calculate, research, no_targets, verify, report
