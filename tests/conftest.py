"""Pytest configuration for API tests.

Creates an isolated SQLite test database and overrides the FastAPI
dependency so TestClient hits the test DB, not production.

Note: the API imports (api.database, api.main) are deferred into the
fixtures so that CI — which doesn't install fastapi/httpx/PyJWT — can
still collect and run the non-API tests without import errors. The API
tests themselves use pytest.importorskip to skip gracefully.
"""
import os
import sys
import tempfile
from pathlib import Path

# Add repo root to sys.path so `dashboard` and `src` are importable.
# Without this, tests/test_dashboard_analysis.py fails with
# ModuleNotFoundError: No module named 'dashboard' in CI.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Point DATABASE_URL at a temp SQLite file BEFORE any api module is imported.
_DB_fd, _DB_PATH = tempfile.mkstemp(suffix=".db")
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH}"
os.environ.setdefault("API_USER", "test@kinzoils.com")
os.environ.setdefault("API_PASSWORD", "testpass")

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


@pytest.fixture(scope="session", autouse=True)
def _create_tables():
    """Create all tables in the test SQLite database."""
    engine = create_engine(f"sqlite:///{_DB_PATH}")
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
    engine = create_engine(f"sqlite:///{_DB_PATH}")
    Session = sessionmaker(bind=engine)
    session = Session()
    for table in ["alerts", "margin_history", "products"]:
        session.execute(text(f"DELETE FROM {table}"))
    session.commit()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session):
    """FastAPI TestClient with the test database injected.

    Deferred import so CI (which doesn't install fastapi) can still
    collect the non-API tests. The API tests use importorskip to
    skip gracefully if fastapi is not available.
    """
    try:
        from api.database import get_db
        from api.main import app
    except ImportError:
        pytest.skip("fastapi not installed — skipping API tests")
    from fastapi.testclient import TestClient

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
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
