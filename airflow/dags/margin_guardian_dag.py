"""
Kinz Margin Guardian — Airflow DAG.

Daily pipeline:
  1. Ingest simulated competitor prices
  2. Validate data quality (price > 0, cogs > 0)
  3. Calculate B2B + B2C margins
  4. Check thresholds and trigger alerts
  5. Send Slack notifications
  6. Cleanup old price data (>90 days)

Schedule: 0 6 * * * (daily at 06:00 UTC = 07:00 Africa/Tunis)

All task callables use Airflow's execution date (context['ds']) instead
of date.today() to ensure correct data alignment with the DAG run.
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta, date, timezone

import pandas as pd
from sqlalchemy import create_engine, text

# Ensure src/ is importable inside Airflow
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from airflow import DAG
from airflow.operators.python import PythonOperator, ShortCircuitOperator
from airflow.utils.dates import days_ago

from src.config import (
    DATABASE_URL,
    SLACK_WEBHOOK_URL,
    DEFAULT_ALERT_THRESHOLD_PCT,
    B2B_DISCOUNT_FACTOR,
    PRICE_RETENTION_DAYS,
)
from src.margin_engine import calculate_margins, check_margin_threshold
from src.alert_manager import send_slack_alert, format_alert_message

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------
# DB helper
# ---------------------------------------------------------------------
def get_engine():
    """Create a SQLAlchemy engine from the DATABASE_URL env var."""
    return create_engine(DATABASE_URL)


def get_execution_date(context: dict) -> date:
    """Extract the execution date from Airflow context.

    Falls back to date.today() if context['ds'] is not available
    (e.g., when testing outside Airflow).
    """
    ds = context.get("ds")
    if ds:
        return datetime.strptime(ds, "%Y-%m-%d").date()
    logger.warning("No 'ds' in context — falling back to date.today()")
    return date.today()


# ---------------------------------------------------------------------
# Task 1: Ingest competitor prices (simulated)
# ---------------------------------------------------------------------
def ingest_competitor_prices(**context):
    """Simulate fetching daily competitor prices for all active products.

    Generates realistic prices by adding ±5% random noise to the product's
    current B2C price. Stores in daily_prices table.
    """
    import numpy as np
    np.random.seed(42)

    engine = get_engine()
    exec_date = get_execution_date(context)

    # Load active products
    products = pd.read_sql(
        "SELECT id, name, b2c_price_tnd FROM products WHERE active = true",
        engine,
    )
    if products.empty:
        logger.warning("No active products found — skipping ingestion.")
        return 0

    # Generate competitor prices (±5% noise around current B2C price)
    prices = []
    for _, row in products.iterrows():
        base_price = float(row["b2c_price_tnd"]) if pd.notna(row["b2c_price_tnd"]) else 30.0
        noise = np.random.uniform(-0.05, 0.05)
        competitor_price = round(base_price * (1 + noise), 3)
        prices.append({
            "product_id": int(row["id"]),
            "price_date": exec_date,
            "competitor_price_tnd": competitor_price,
            "source": "simulated",
        })

    df = pd.DataFrame(prices)

    # Upsert into daily_prices (avoid duplicates for same product + date)
    with engine.begin() as conn:
        # Delete existing entries for this execution date (idempotent re-run)
        conn.execute(
            text("DELETE FROM daily_prices WHERE price_date = :d"),
            {"d": exec_date},
        )
        df.to_sql("daily_prices", conn, if_exists="append", index=False)

    logger.info(f"Ingested {len(df)} competitor prices for {exec_date}")
    return len(df)


# ---------------------------------------------------------------------
# Task 2: Validate ingested data (ShortCircuit — skip downstream if invalid)
# ---------------------------------------------------------------------
def validate_ingested_data(**context):
    """Validate that all ingested prices > 0 and all product COGS > 0.

    Checks the last 30 days of data (not just the execution date) to
    be resilient to backfill scenarios and manual seed scripts.

    Uses ShortCircuitOperator: returns False to skip downstream tasks
    if data quality check fails (instead of crashing the DAG).
    """
    engine = get_engine()
    exec_date = get_execution_date(context)

    # Check daily_prices — look at the last 30 days for robustness
    prices_df = pd.read_sql(
        text("SELECT * FROM daily_prices WHERE price_date >= CURRENT_DATE - INTERVAL '30 days'"),
        engine,
    )

    if prices_df.empty:
        logger.error(
            f"DATA QUALITY FAIL: No prices found in the last 30 days "
            f"(execution date: {exec_date}) — skipping margin calculation."
        )
        return False

    # Check competitor_price > 0
    invalid_prices = prices_df[prices_df["competitor_price_tnd"] <= 0]
    if not invalid_prices.empty:
        logger.error(
            f"DATA QUALITY FAIL: {len(invalid_prices)} prices are <= 0 — "
            f"products: {invalid_prices['product_id'].tolist()}"
        )
        return False

    # Check that all products with prices have COGS > 0
    products_df = pd.read_sql(
        text(
            "SELECT id, name, cogs_tnd FROM products WHERE active = true AND id IN "
            "(SELECT product_id FROM daily_prices WHERE price_date >= CURRENT_DATE - INTERVAL '30 days')"
        ),
        engine,
    )

    invalid_cogs = products_df[products_df["cogs_tnd"] <= 0]
    if not invalid_cogs.empty:
        logger.error(
            f"DATA QUALITY FAIL: {len(invalid_cogs)} products have COGS <= 0 — "
            f"products: {invalid_cogs['name'].tolist()}"
        )
        return False

    logger.info(
        f"DATA QUALITY PASS: {len(prices_df)} prices validated (last 30 days), "
        f"{len(products_df)} products with valid COGS. Execution date: {exec_date}"
    )
    return True


# ---------------------------------------------------------------------
# Task 3: Calculate margins
# ---------------------------------------------------------------------
def calculate_margins_task(**context):
    """Calculate B2B + B2C margins for all products with prices on the execution date."""
    engine = get_engine()
    exec_date = get_execution_date(context)

    query = text("""
        SELECT p.id, p.name, p.cogs_tnd, p.alert_threshold_pct,
               dp.competitor_price_tnd, dp.price_date
        FROM products p
        JOIN daily_prices dp ON p.id = dp.product_id
        WHERE dp.price_date = :d AND p.active = true
    """)

    with engine.connect() as conn:
        result = conn.execute(query, {"d": exec_date})
        rows = result.fetchall()

    if not rows:
        # Fallback: if no data for the exact execution date, use the most recent prices
        logger.warning(
            f"No prices found for execution date {exec_date}. "
            f"Falling back to most recent prices for each product."
        )
        fallback_query = text("""
            SELECT p.id, p.name, p.cogs_tnd, p.alert_threshold_pct,
                   dp.competitor_price_tnd, dp.price_date
            FROM products p
            JOIN daily_prices dp ON p.id = dp.product_id
            WHERE p.active = true
              AND dp.price_date = (
                  SELECT MAX(price_date) FROM daily_prices
                  WHERE product_id = p.id
              )
        """)
        with engine.connect() as conn:
            result = conn.execute(fallback_query)
            rows = result.fetchall()

    if not rows:
        logger.warning("No data to calculate margins for — even with fallback.")
        return 0

    margin_records = []
    for row in rows:
        product_id = row[0]
        _product_name = row[1]  # noqa: F841
        cogs = float(row[2])
        _threshold = float(row[3]) if row[3] else DEFAULT_ALERT_THRESHOLD_PCT
        competitor_price = float(row[4])
        # Use the actual price_date from the row (may differ from exec_date in fallback)
        calc_date = row[5] if len(row) > 5 else exec_date

        b2c_price, b2b_price, b2c_margin, b2b_margin = calculate_margins(
            cogs, competitor_price, B2B_DISCOUNT_FACTOR
        )

        margin_records.append({
            "product_id": product_id,
            "calc_date": calc_date,
            "b2c_margin_pct": b2c_margin,
            "b2b_margin_pct": b2b_margin,
            "b2c_price_tnd": b2c_price,
            "b2b_price_tnd": b2b_price,
            "cogs_tnd": cogs,
        })

    df = pd.DataFrame(margin_records)

    with engine.begin() as conn:
        # Delete existing for the execution date (idempotent)
        conn.execute(
            text("DELETE FROM margin_history WHERE calc_date = :d"),
            {"d": exec_date},
        )
        df.to_sql("margin_history", conn, if_exists="append", index=False)

    logger.info(f"Calculated margins for {len(df)} products on {exec_date}")
    return len(df)


# ---------------------------------------------------------------------
# Task 4: Check thresholds + create alert records
# ---------------------------------------------------------------------
def check_thresholds_task(**context):
    """Check if any margins are below threshold — create alert records."""
    engine = get_engine()
    exec_date = get_execution_date(context)

    # Try execution date first, then fall back to the latest available
    query = text("""
        SELECT mh.product_id, p.name, mh.b2c_margin_pct, mh.b2b_margin_pct,
               p.alert_threshold_pct, mh.cogs_tnd, mh.b2c_price_tnd, mh.b2b_price_tnd
        FROM margin_history mh
        JOIN products p ON mh.product_id = p.id
        WHERE mh.calc_date = :d
    """)

    with engine.connect() as conn:
        result = conn.execute(query, {"d": exec_date})
        rows = result.fetchall()

    if not rows:
        # Fallback: use the latest margin_history entries
        logger.warning(
            f"No margin history for execution date {exec_date}. "
            f"Falling back to most recent margins."
        )
        fallback_query = text("""
            SELECT mh.product_id, p.name, mh.b2c_margin_pct, mh.b2b_margin_pct,
                   p.alert_threshold_pct, mh.cogs_tnd, mh.b2c_price_tnd, mh.b2b_price_tnd
            FROM margin_history mh
            JOIN products p ON mh.product_id = p.id
            WHERE mh.calc_date = (SELECT MAX(calc_date) FROM margin_history)
        """)
        with engine.connect() as conn:
            result = conn.execute(fallback_query)
            rows = result.fetchall()

    if not rows:
        logger.warning("No margin history found at all — skipping threshold check.")
        ti = context["ti"]
        ti.xcom_push(key="alert_data", value=[])
        return 0

    alerts_created = 0
    alert_data = []  # Store for the Slack task

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
            alerts_created += 1

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
            alerts_created += 1

    # Insert alerts into the alerts table
    if alert_data:
        alerts_df = pd.DataFrame(alert_data)
        alerts_db = alerts_df[["product_id", "alert_type", "margin_pct", "threshold_pct", "message"]].copy()
        alerts_db["notified"] = False

        with engine.begin() as conn:
            alerts_db.to_sql("alerts", conn, if_exists="append", index=False)

    # Push alert data to XCom for the Slack task
    ti = context["ti"]
    ti.xcom_push(key="alert_data", value=alert_data)

    logger.info(f"Created {alerts_created} alerts for {exec_date}")
    return alerts_created


# ---------------------------------------------------------------------
# Task 5: Send Slack alerts
# ---------------------------------------------------------------------
def send_slack_alerts_task(**context):
    """Send Slack notifications for all alerts created in this run."""
    ti = context["ti"]
    alert_data = ti.xcom_pull(key="alert_data", task_ids="check_thresholds")

    if not alert_data:
        logger.info("No alerts to send — skipping Slack notification.")
        return 0

    webhook_url = SLACK_WEBHOOK_URL or os.getenv("SLACK_WEBHOOK_URL", "")
    sent_count = 0

    for alert in alert_data:
        success = send_slack_alert(
            webhook_url=webhook_url if webhook_url else None,
            product_name=alert["product_name"],
            alert_type=alert["alert_type"],
            margin_pct=alert["margin_pct"],
            threshold_pct=alert["threshold_pct"],
            cogs=alert["cogs"],
            price=alert["price"],
        )
        if success:
            sent_count += 1

    # Mark alerts as notified
    engine = get_engine()
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE alerts SET notified = true WHERE notified = false AND alert_date >= :d"),
            {"d": now_str},
        )

    logger.info(f"Sent {sent_count} Slack alerts")
    return sent_count


# ---------------------------------------------------------------------
# Task 6: Cleanup old prices
# ---------------------------------------------------------------------
def cleanup_old_prices_task(**context):
    """Delete daily_prices older than PRICE_RETENTION_DAYS (default 90)."""
    engine = get_engine()
    exec_date = get_execution_date(context)
    cutoff = exec_date - timedelta(days=PRICE_RETENTION_DAYS)

    with engine.begin() as conn:
        result = conn.execute(
            text("DELETE FROM daily_prices WHERE price_date < :d"),
            {"d": cutoff},
        )
        deleted = result.rowcount

    logger.info(f"Cleaned up {deleted} old price records (older than {cutoff})")
    return deleted


# ---------------------------------------------------------------------
# DAG definition
# ---------------------------------------------------------------------
default_args = {
    "owner": "kinz",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

dag = DAG(
    dag_id="margin_guardian",
    description="Daily margin calculation and alerting for KINZ products",
    default_args=default_args,
    schedule="0 6 * * *",
    start_date=days_ago(1),
    catchup=False,
    tags=["kinz", "margin", "alerting"],
)

# Task definitions
t1 = PythonOperator(
    task_id="ingest_competitor_prices",
    python_callable=ingest_competitor_prices,
    dag=dag,
)

t2 = ShortCircuitOperator(
    task_id="validate_ingested_data",
    python_callable=validate_ingested_data,
    dag=dag,
)

t3 = PythonOperator(
    task_id="calculate_margins",
    python_callable=calculate_margins_task,
    dag=dag,
)

t4 = PythonOperator(
    task_id="check_thresholds",
    python_callable=check_thresholds_task,
    dag=dag,
)

t5 = PythonOperator(
    task_id="send_slack_alerts",
    python_callable=send_slack_alerts_task,
    dag=dag,
)

t6 = PythonOperator(
    task_id="cleanup_old_prices",
    python_callable=cleanup_old_prices_task,
    dag=dag,
)

# Task dependencies
t1 >> t2 >> t3 >> t4 >> t5 >> t6
