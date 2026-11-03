from collections.abc import Iterator
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings, get_settings
from app.core.security import create_access_token
from app.db.base import Base
from app.db.session import get_session
from app.main import app
from app.models.portfolio import Portfolio
from app.models.user import User


@pytest.fixture
def db_session() -> Iterator[Session]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def api_context(db_session: Session):
    settings = Settings(secret_key="test-secret-key-with-more-than-32-characters")
    user = User(email="owner@example.com", password_hash="unused")
    db_session.add(user)
    db_session.flush()
    portfolio = Portfolio(user_id=user.id, name="Long-term", base_currency="INR")
    db_session.add(portfolio)
    db_session.commit()

    def session_override():
        yield db_session

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[get_settings] = lambda: settings
    token = create_access_token(user.id, settings)
    with TestClient(app) as client:
        yield client, user, portfolio, {"Authorization": f"Bearer {token}"}, db_session
    app.dependency_overrides.clear()
