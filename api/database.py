"""SQLAlchemy database connection.

The engine is created by the shared toolkit ``astk.db.make_engine`` rather than
a local ``create_engine`` call: it is cached per URL, defaults to
``pool_pre_ping=True``, and is SQLite-in-memory safe (``StaticPool`` +
``check_same_thread=False``) so tests that point ``DATABASE_URL`` at SQLite
behave the same as production Postgres. ``healthcheck``/``wait_for_db`` from the
same module back the ``/health`` endpoint and the startup readiness check.
"""
from __future__ import annotations

from astk.db import make_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from src.config import DATABASE_URL

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
