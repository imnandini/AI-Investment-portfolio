from typing import TypedDict


class ReviewState(TypedDict, total=False):
    portfolio_id: str
    user_id: str
    analytics: dict
    targets: list[dict]
    holdings: list[dict]
    portfolio_name: str
    pf_account_count: int
    company_reviews: list[dict]
    coverage: dict
    evidence: list[dict]
    limitations: list[str]
    activities: list[str]
    report: dict
