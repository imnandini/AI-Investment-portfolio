from typing import TypedDict


class ReviewState(TypedDict, total=False):
    portfolio_id: str
    user_id: str
    analytics: dict
    targets: list[str]
    evidence: list[dict]
    limitations: list[str]
    activities: list[str]
    report: dict
