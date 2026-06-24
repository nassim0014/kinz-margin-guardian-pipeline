"""Kinz Margin Guardian Pipeline — shared configuration."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://kinz_guardian:change_me_in_prod@localhost:5432/margin_guardian",
)

JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-change-me-in-production-please")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")

# Margin defaults
DEFAULT_ALERT_THRESHOLD_PCT = 40.0
B2B_DISCOUNT_FACTOR = 0.85  # B2B price = competitor price × 0.85

# Data retention
PRICE_RETENTION_DAYS = 90
