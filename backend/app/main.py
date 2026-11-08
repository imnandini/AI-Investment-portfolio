from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.analytics import router as analytics_router
from app.api.auth import router as auth_router
from app.api.financial_data import router as financial_data_router
from app.api.holdings import router as holdings_router
from app.api.portfolios import router as portfolios_router
from app.api.documents import router as documents_router
from app.api.companies import router as companies_router
from app.api.prices import router as prices_router
from app.api.reviews import router as reviews_router
from app.api.chat import router as chat_router
from app.api.mcp import router as mcp_router
from app.api.indmoney import router as indmoney_router
from app.api.briefs import router as briefs_router
from app.middleware.security import SecurityMiddleware
from app.core.config import get_settings
from app.db.session import dispose_database, initialize_database


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Own the shared database engine for the lifetime of the application."""
    initialize_database(get_settings())
    try:
        yield
    finally:
        dispose_database()


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "A research and risk-analysis assistant. It does not provide automated "
        "investment advice or execute transactions."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.add_middleware(SecurityMiddleware, limit=settings.request_limit_per_minute)

app.include_router(health_router)
app.include_router(analytics_router)
app.include_router(auth_router)
app.include_router(financial_data_router)
app.include_router(portfolios_router)
app.include_router(holdings_router)
app.include_router(documents_router)
app.include_router(companies_router)
app.include_router(prices_router)
app.include_router(reviews_router)
app.include_router(chat_router)
app.include_router(mcp_router)
app.include_router(indmoney_router)
app.include_router(briefs_router)
