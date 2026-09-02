"""Kinz Margin Guardian Pipeline — shared configuration.

Settings now flow through the shared toolkit's ``astk.settings.BaseServiceSettings``
instead of bare ``os.getenv`` calls: values are validated once, secrets are
redacted in ``repr()``, and a bad ``.env`` yields a readable "missing / invalid"
message instead of a traceback. db and alerting already sit on ``astk`` (see
``api/database.py`` and ``src/alert_manager.py``); this brings settings in line.

The module-level constants below (``DATABASE_URL``, ``JWT_SECRET`` …) are kept as
thin aliases over the ``settings`` object so existing importers keep working
unchanged — they are now validated and env-overridable uniformly.
"""
from __future__ import annotations

from pathlib import Path

from astk.settings import BaseServiceSettings, load_settings

ROOT = Path(__file__).resolve().parent.parent


class GuardianSettings(BaseServiceSettings):
    """Margin-guardian settings: the shared base plus this service's own fields.

    ``database_url`` is deliberately widened from the base's ``PostgresDsn`` back
    to ``str``: this service runs on Postgres in production but the test suite
    (``tests/conftest.py``) points ``DATABASE_URL`` at a SQLite file, and
    ``astk.db.make_engine`` is SQLite-safe by design. The stricter ``PostgresDsn``
    type would reject that test URL at load time, so ``str`` is the correct type
    for a service that must accept both.
    """

    app_name: str = "margin-guardian"

    # Postgres in prod, SQLite in tests — see class docstring.
    database_url: str | None = (
        "postgresql+psycopg2://kinz_guardian:change_me_in_prod@localhost:5432/margin_guardian"
    )

    # Auth
    jwt_secret: str = "dev-only-change-me-in-production-please"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # Margin defaults (now env-overridable; same values as before)
    default_alert_threshold_pct: float = 40.0
    b2b_discount_factor: float = 0.85  # B2B price = competitor price × 0.85

    # Data retention
    price_retention_days: int = 90


settings = load_settings(GuardianSettings)

# ---------------------------------------------------------------------------
# Backward-compatible module constants (thin aliases over ``settings``).
# Existing imports like ``from src.config import DATABASE_URL`` keep working.
# ---------------------------------------------------------------------------
DATABASE_URL = settings.database_url

JWT_SECRET = settings.jwt_secret
JWT_ALGORITHM = settings.jwt_algorithm
JWT_EXPIRE_MINUTES = settings.jwt_expire_minutes

SLACK_WEBHOOK_URL = settings.slack_webhook() or ""

DEFAULT_ALERT_THRESHOLD_PCT = settings.default_alert_threshold_pct
B2B_DISCOUNT_FACTOR = settings.b2b_discount_factor

PRICE_RETENTION_DAYS = settings.price_retention_days
