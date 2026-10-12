"""SQLAlchemy database connection.

The engine is created by the shared toolkit ``astk.db.make_engine`` rather than
a local ``create_engine`` call: it is cached per URL, defaults to
``pool_pre_ping=True``, and is SQLite-in-memory safe (``StaticPool`` +
``check_same_thread=False``) so tests that point ``DATABASE_URL`` at SQLite
behave the same as production Postgres. ``healthcheck``/``wait_for_db`` from the
same module back the ``/health`` endpoint and the startup readiness check.

astk lives in the private ``analytics-service-toolkit`` repo. Production images
install it via a BuildKit secret, but the lightweight CI environment does not
(same shape as ``src/config.py`` and ``src/alert_manager.py``). Without a
fallback here, this module's bare ``from astk.db import make_engine`` raised
``ModuleNotFoundError`` at import time, which ``tests/conftest.py``'s ``client``
fixture caught and turned into ``pytest.skip("fastapi not installed - skipping
API tests")`` - fastapi *was* installed; the real cause was this missing astk,
and the skip reason said otherwise. Degrade gracefully instead, mirroring the
two behaviors the docstring above promises (``pool_pre_ping=True``, SQLite-safe
via ``StaticPool`` + ``check_same_thread=False``); astk's per-URL engine caching
isn't replicated since this module only calls ``make_engine`` once, at import.
"""
from __future__ import annotations

from sqlalchemy.orm import sessionmaker, DeclarativeBase

from src.config import DATABASE_URL

try:
    from astk.db import make_engine
except ModuleNotFoundError:  # pragma: no cover - exercised only in the lightweight CI env
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool

    def make_engine(url: str):
        kwargs: dict = {"pool_pre_ping": True}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
            kwargs["poolclass"] = StaticPool
        return create_engine(url, **kwargs)

engine = make_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency: yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
