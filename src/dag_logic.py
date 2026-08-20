"""Pure logic extracted from the Airflow DAG (item 3).

These functions are the testable parts of margin_guardian_dag.py —
validation, margin-record building, and alert-data building. They have
no database or Airflow dependencies, so they can be unit-tested without
a running Airflow instance or Postgres.

Pattern: the DAG imports these and calls them inside its task callables,
leaving only the DB I/O and Airflow operator wiring in the DAG file.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pandas as pd

from src.config import B2B_DISCOUNT_FACTOR, DEFAULT_ALERT_THRESHOLD_PCT
from src.margin_engine import calculate_margins, check_margin_threshold


def get_execution_date(context: dict) -> date:
    """Extract the execution date from Airflow context.

    Falls back to date.today() if context['ds'] is not available
    (e.g., when testing outside Airflow).
    """
    ds = context.get("ds")
    if ds:
        return datetime.strptime(ds, "%Y-%m-%d").date()
    return date.today()


def validate_price_data(
    prices_df: pd.DataFrame,
    products_df: pd.DataFrame,
) -> tuple[bool, str]:
    """Validate that all prices > 0 and all product COGS > 0.

    Args:
        prices_df: DataFrame of daily prices (must have
            'competitor_price_tnd' and 'product_id' columns).
        products_df: DataFrame of products (must have 'id', 'name',
            'cogs_tnd' columns).

    Returns:
        (is_valid, reason) — is_valid is True if all checks pass, False
        otherwise. reason is a human-readable string explaining why
        validation failed (empty string if valid).
    """
    if prices_df.empty:
        return False, "No prices found in the lookback window."

    invalid_prices = prices_df[prices_df["competitor_price_tnd"] <= 0]
    if not invalid_prices.empty:
        product_ids = invalid_prices["product_id"].tolist()
        return False, (
            f"{len(invalid_prices)} prices are <= 0 — "
            f"products: {product_ids}"
        )

    if products_df.empty:
        return False, "No products with prices found."

    invalid_cogs = products_df[products_df["cogs_tnd"] <= 0]
    if not invalid_cogs.empty:
        names = invalid_cogs["name"].tolist()
        return False, (
            f"{len(invalid_cogs)} products have COGS <= 0 — "
            f"products: {names}"
        )

    return True, ""


def build_margin_records(
    rows: list[tuple],
    exec_date: date,
) -> list[dict[str, Any]]:
    """Build margin record dicts from DB query rows.

    Each row is expected to be a tuple of:
        (product_id, product_name, cogs_tnd, alert_threshold_pct,
         competitor_price_tnd, price_date)

    Args:
        rows: Query result rows.
        exec_date: Fallback calc_date if the row has no price_date.

    Returns:
        List of margin record dicts suitable for to_sql insertion.
    """
    records = []
    for row in rows:
        product_id = row[0]
        cogs = float(row[2])
        competitor_price = float(row[4])
        calc_date = row[5] if len(row) > 5 else exec_date

        b2c_price, b2b_price, b2c_margin, b2b_margin = calculate_margins(
            cogs, competitor_price, B2B_DISCOUNT_FACTOR
        )

        records.append({
            "product_id": product_id,
            "calc_date": calc_date,
            "b2c_margin_pct": b2c_margin,
            "b2b_margin_pct": b2b_margin,
            "b2c_price_tnd": b2c_price,
            "b2b_price_tnd": b2b_price,
            "cogs_tnd": cogs,
        })

    return records


def build_alert_data(
    rows: list[tuple],
) -> list[dict[str, Any]]:
    """Build alert data dicts from margin-history query rows.

    Each row is expected to be a tuple of:
        (product_id, product_name, b2c_margin_pct, b2b_margin_pct,
         alert_threshold_pct, cogs_tnd, b2c_price_tnd, b2b_price_tnd)

    Returns:
        List of alert dicts — one per margin that fell below threshold.
        Each dict has: product_id, alert_type, margin_pct, threshold_pct,
        message, product_name, cogs, price.
    """
    from src.alert_manager import format_alert_message

    alert_data = []

    for row in rows:
        product_id = row[0]
        product_name = row[1]
        b2c_margin = float(row[2])
        b2b_margin = float(row[3])
        threshold = float(row[4]) if row[4] else DEFAULT_ALERT_THRESHOLD_PCT
        cogs = float(row[5])
        b2c_price = float(row[6])
        b2b_price = float(row[7])

        b2c_alert, b2b_alert = check_margin_threshold(b2c_margin, b2b_margin, threshold)

        if b2c_alert:
            msg = format_alert_message(product_name, "B2C", b2c_margin, threshold)
            alert_data.append({
                "product_id": product_id,
                "alert_type": "B2C",
                "margin_pct": b2c_margin,
                "threshold_pct": threshold,
                "message": msg,
                "product_name": product_name,
                "cogs": cogs,
                "price": b2c_price,
            })

        if b2b_alert:
            msg = format_alert_message(product_name, "B2B", b2b_margin, threshold)
            alert_data.append({
                "product_id": product_id,
                "alert_type": "B2B",
                "margin_pct": b2b_margin,
                "threshold_pct": threshold,
                "message": msg,
                "product_name": product_name,
                "cogs": cogs,
                "price": b2b_price,
            })

    return alert_data
