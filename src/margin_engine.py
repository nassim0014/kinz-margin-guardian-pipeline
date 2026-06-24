"""
Kinz Margin Guardian — Core margin calculation engine.

Functions:
  - calculate_margins: compute B2B + B2C margins given COGS and competitor price
  - check_margin_threshold: compare margins against configurable thresholds
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.config import B2B_DISCOUNT_FACTOR, DEFAULT_ALERT_THRESHOLD_PCT


@dataclass
class MarginResult:
    """Container for a single product's margin calculation."""
    product_id: int
    product_name: str
    cogs_tnd: float
    competitor_price_tnd: float
    b2c_price_tnd: float
    b2b_price_tnd: float
    b2c_margin_pct: float
    b2b_margin_pct: float
    threshold_pct: float
    b2c_alert: bool
    b2b_alert: bool


def calculate_margins(
    cogs: float,
    competitor_price: float,
    b2b_discount: float = B2B_DISCOUNT_FACTOR,
) -> tuple[float, float, float, float]:
    """Calculate B2B and B2C margins.

    Parameters
    ----------
    cogs : float
        Cost of Goods Sold in TND.
    competitor_price : float
        Today's competitor price in TND (used as B2C price).
    b2b_discount : float
        B2B price = competitor_price × b2b_discount. Default 0.85 (15% off).

    Returns
    -------
    tuple (b2c_price, b2b_price, b2c_margin_pct, b2b_margin_pct)
    """
    b2c_price = competitor_price
    b2b_price = competitor_price * b2b_discount

    b2c_margin_pct = ((b2c_price - cogs) / b2c_price * 100) if b2c_price > 0 else 0.0
    b2b_margin_pct = ((b2b_price - cogs) / b2b_price * 100) if b2b_price > 0 else 0.0

    return b2c_price, b2b_price, round(b2c_margin_pct, 2), round(b2b_margin_pct, 2)


def check_margin_threshold(
    b2c_margin_pct: float,
    b2b_margin_pct: float,
    threshold_pct: float = DEFAULT_ALERT_THRESHOLD_PCT,
) -> tuple[bool, bool]:
    """Check whether margins fall below the alert threshold.

    Returns
    -------
    tuple (b2c_alert, b2b_alert) — True if margin < threshold
    """
    return b2c_margin_pct < threshold_pct, b2b_margin_pct < threshold_pct


def compute_product_margins(
    product_id: int,
    product_name: str,
    cogs: float,
    competitor_price: float,
    threshold_pct: float = DEFAULT_ALERT_THRESHOLD_PCT,
    b2b_discount: float = B2B_DISCOUNT_FACTOR,
) -> MarginResult:
    """Full margin calculation + threshold check for a single product."""
    b2c_price, b2b_price, b2c_margin, b2b_margin = calculate_margins(
        cogs, competitor_price, b2b_discount
    )
    b2c_alert, b2b_alert = check_margin_threshold(b2c_margin, b2b_margin, threshold_pct)

    return MarginResult(
        product_id=product_id,
        product_name=product_name,
        cogs_tnd=cogs,
        competitor_price_tnd=competitor_price,
        b2c_price_tnd=b2c_price,
        b2b_price_tnd=b2b_price,
        b2c_margin_pct=b2c_margin,
        b2b_margin_pct=b2b_margin,
        threshold_pct=threshold_pct,
        b2c_alert=b2c_alert,
        b2b_alert=b2b_alert,
    )
