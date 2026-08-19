"""
Kinz Margin Guardian — Alert manager.

Sends notifications via Slack webhook when margins drop below thresholds.
Falls back to logging if no webhook is configured.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


def send_slack_alert(
    webhook_url: Optional[str],
    product_name: str,
    alert_type: str,
    margin_pct: float,
    threshold_pct: float,
    cogs: float,
    price: float,
) -> bool:
    """Send a Slack alert via incoming webhook.

    Parameters
    ----------
    webhook_url : str or None
        The Slack incoming webhook URL. If None or empty, logs the alert instead.
    product_name : str
    alert_type : str
        'B2B' or 'B2C'.
    margin_pct : float
    threshold_pct : float
    cogs : float
    price : float

    Returns
    -------
    bool — True if alert was sent (or logged), False on error.
    """
    message = (
        f"⚠️ *Margin Alert: {product_name}*\n"
        f"*Type:* {alert_type}\n"
        f"*Margin:* {margin_pct:.2f}% (threshold: {threshold_pct:.0f}%)\n"
        f"*COGS:* {cogs:.3f} TND | *Price:* {price:.3f} TND\n"
        f"*Time:* {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
    )

    if not webhook_url:
        logger.warning(f"[ALERT] No Slack webhook configured — logging only:\n{message}")
        print(f"\n{'='*60}\n{message}\n{'='*60}\n")
        return True

    try:
        payload = json.dumps({"text": message}).encode("utf-8")
        req = Request(webhook_url, data=payload, headers={"Content-Type": "application/json"})
        with urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                logger.info(f"[ALERT] Slack alert sent for {product_name} ({alert_type})")
                return True
            else:
                logger.error(f"[ALERT] Slack returned {resp.status}")
                return False
    except Exception as e:
        logger.error(f"[ALERT] Failed to send Slack alert: {e}")
        print(f"\n{'='*60}\n{message}\n{'='*60}\n")
        return True  # Still return True so the alert is logged in DB


def format_alert_message(
    product_name: str,
    alert_type: str,
    margin_pct: float,
    threshold_pct: float,
) -> str:
    """Format a human-readable alert message for database storage."""
    return (
        f"{alert_type} margin for {product_name} dropped to {margin_pct:.2f}% "
        f"(threshold: {threshold_pct:.0f}%)"
    )
