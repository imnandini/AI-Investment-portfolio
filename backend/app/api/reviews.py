from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.auth import CurrentUser
from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.models.review import PortfolioReview
from app.services.prices import require_portfolio
from app.agents.portfolio_review.graph import build_review_graph

router = APIRouter(prefix="/portfolios/{portfolio_id}/reviews", tags=["portfolio reviews"])
DB = Annotated[Session, Depends(get_session)]


def serialize(review):
    return {"id": review.id, "portfolio_id": review.portfolio_id, "status": review.status, "created_at": review.created_at, "report": review.report}


@router.post("", status_code=201)
async def launch_review(portfolio_id: UUID, session: DB, user: CurrentUser, settings: Annotated[Settings, Depends(get_settings)]):
    require_portfolio(session, user.id, portfolio_id)
    review = PortfolioReview(user_id=user.id, portfolio_id=portfolio_id, status="running")
    session.add(review)
    session.commit()
    try:
        result = await build_review_graph(session, settings).ainvoke({"user_id": str(user.id), "portfolio_id": str(portfolio_id)}, {"recursion_limit": 10})
        review.report = result["report"]
        review.status = review.report["assessment_status"]
    except Exception:
        session.rollback()
        review.status = "failed"
        review.report = {"error": "The review could not finish. Please retry; no conclusions were generated."}
    session.commit()
    return serialize(review)


@router.get("")
def review_history(portfolio_id: UUID, session: DB, user: CurrentUser):
    require_portfolio(session, user.id, portfolio_id)
    return [serialize(row) for row in session.scalars(select(PortfolioReview).where(PortfolioReview.portfolio_id == portfolio_id, PortfolioReview.user_id == user.id).order_by(PortfolioReview.created_at.desc()).limit(50))]


@router.get("/{review_id}")
def read_review(portfolio_id: UUID, review_id: UUID, session: DB, user: CurrentUser):
    require_portfolio(session, user.id, portfolio_id)
    row = session.scalar(select(PortfolioReview).where(PortfolioReview.id == review_id, PortfolioReview.portfolio_id == portfolio_id, PortfolioReview.user_id == user.id))
    if not row:
        raise HTTPException(404, "Review not found.")
    return serialize(row)


@router.delete("/{review_id}", status_code=204)
def delete_review(portfolio_id: UUID, review_id: UUID, session: DB, user: CurrentUser):
    read_review(portfolio_id, review_id, session, user)
    session.delete(session.get(PortfolioReview, review_id))
    session.commit()
