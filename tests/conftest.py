"""Pytest configuration for API tests.

Creates an isolated SQLite test database and overrides the FastAPI
dependency so TestClient hits the test DB, not production.
"""
import os
import tempfile

# Point DATABASE_URL at a temp SQLite file BEFORE any api module is imported.
# api/database.py creates the engine at import time from DATABASE_URL.
_DB_fd, _DB_PATH = tempfile.mkstemp(suffix=".db")
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH}"
os.environ.setdefault("API_USER", "test@kinzoils.com")
os.environ.setdefault("API_PASSWORD", "testpass")

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from api.database import get_db
from api.main import app


@pytest.fixture(scope="session", autouse=True)
def _create_tables():
    """Create all tables in the test SQLite database."""
    engine = create_engine(f"sqlite:///{_DB_PATH}")
    # SQLite-compatible DDL (adapted from scripts/init_db.sql)
    statements = [
        "CREATE TABLE IF NOT EXISTS products ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  name VARCHAR(255) NOT NULL,"
        "  category VARCHAR(100),"
        "  cogs_tnd NUMERIC(10, 3) NOT NULL,"
        "  b2b_price_tnd NUMERIC(10, 3),"
        "  b2c_price_tnd NUMERIC(10, 3),"
        "  alert_threshold_pct NUMERIC(5, 2) DEFAULT 40.00,"
        "  active BOOLEAN DEFAULT TRUE,"
        "  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,"
        "  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        ")",
        "CREATE TABLE IF NOT EXISTS margin_history ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,"
        "  calc_date DATE NOT NULL,"
        "  b2c_margin_pct NUMERIC(5, 2),"
        "  b2b_margin_pct NUMERIC(5, 2),"
        "  b2c_price_tnd NUMERIC(10, 3),"
        "  b2b_price_tnd NUMERIC(10, 3),"
        "  cogs_tnd NUMERIC(10, 3),"
        "  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,"
        "  UNIQUE(product_id, calc_date)"
        ")",
        "CREATE TABLE IF NOT EXISTS alerts ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,"
        "  alert_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,"
        "  alert_type VARCHAR(20),"
        "  margin_pct NUMERIC(5, 2),"
        "  threshold_pct NUMERIC(5, 2),"
        "  message TEXT,"
        "  notified BOOLEAN DEFAULT FALSE"
        ")",
    ]
    with engine.connect() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
        conn.commit()
    yield
    import os as _os
    _os.close(_DB_fd)
    _os.unlink(_DB_PATH)


@pytest.fixture
def db_session():
    """Yield a database session for direct DB manipulation in tests.

    Cleans up all tables before each test so tests are isolated.
    """
    from sqlalchemy import text
    engine = create_engine(f"sqlite:///{_DB_PATH}")
    Session = sessionmaker(bind=engine)
    session = Session()
    # Clean up any data left by previous tests
    for table in ["alerts", "margin_history", "products"]:
        session.execute(text(f"DELETE FROM {table}"))
    session.commit()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session):
    """FastAPI TestClient with the test database injected."""
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    from fastapi.testclient import TestClient
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def auth_token(client):
    """Get a valid JWT token for authenticated requests."""
    response = client.post("/auth/token", json={
        "email": "test@kinzoils.com",
        "password": "testpass",
    })
    return response.json()["access_token"]


@pytest.fixture
def auth_headers(auth_token):
    """Authorization headers for authenticated requests."""
    return {"Authorization": f"Bearer {auth_token}"}
