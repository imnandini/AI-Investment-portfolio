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

app.include_router(health_router)
app.include_router(analytics_router)
app.include_router(auth_router)
app.include_router(financial_data_router)
app.include_router(portfolios_router)
app.include_router(holdings_router)
