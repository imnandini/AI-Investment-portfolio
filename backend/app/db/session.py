from collections.abc import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def initialize_database(settings: Settings) -> Engine:
    """Create the shared engine and session factory without connecting eagerly."""
    global _engine, _session_factory

    dispose_database()
    _engine = create_engine(
        settings.database_url,
        echo=settings.database_echo,
        pool_pre_ping=True,
    )
    _session_factory = sessionmaker(
        bind=_engine,
        autoflush=False,
        expire_on_commit=False,
    )
    return _engine


def get_session() -> Iterator[Session]:
    """Yield a request-scoped session and always return its connection to the pool."""
    if _session_factory is None:
        raise RuntimeError("Database has not been initialized for this application.")

    with _session_factory() as session:
        yield session


def dispose_database() -> None:
    """Close pooled connections and clear the shared engine/session factory."""
    global _engine, _session_factory

    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
