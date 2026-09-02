"""
Kinz Margin Guardian — Alert manager.

Sends notifications via Slack when margins drop below thresholds, falling back
to logging when no webhook is configured or delivery fails.

Delivery is delegated to the shared toolkit ``astk.alerts`` rather than a
hand-rolled ``urllib`` POST. astk's ``SlackNotifier`` retries on 429/5xx with
exponential backoff and **never raises into the caller** — a broken alert
channel must not take down the pipeline that is trying to warn about a margin
problem. This is the shared substrate that competitor-intelligence,
secure-commerce-hub and accounting-analysis are meant to build on too, so the
retry/backoff logic lives (and is tested) in one place.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

# astk lives in the private ``analytics-service-toolkit`` repo. Production
# images install it via a BuildKit secret, but the lightweight CI environment
# (and anything that only needs the pure helper ``format_alert_message`` — e.g.
# the Airflow DAG logic in ``src/dag_logic.py``) does not. Degrade gracefully:
# import it when available, and let the delivery helpers fail loudly only if
# they are actually called without it. ``send_slack_alert`` already treats a
# missing/broken notifier as "log instead, never raise".
try:
    from astk.alerts import Alert, SlackNotifier
except ModuleNotFoundError:  # pragma: no cover - exercised only in the lightweight CI env
    Alert = None
    SlackNotifier = None

logger = logging.getLogger(__name__)


def _severity_for(margin_pct: float) -> str:
    """A negative margin means we're selling below cost — that's critical, not
    just a threshold breach. Everything else that reaches this function has
    already crossed a configured threshold, so it's a warning."""
    return "critical" if margin_pct < 0 else "warning"


def _build_alert(
    product_name: str,
    alert_type: str,
    margin_pct: float,
    threshold_pct: float,
    cogs: float,
    price: float,
) -> Alert:
    return Alert(
        title=f"Margin Alert: {product_name}",
        body=(
            f"{alert_type} margin dropped to {margin_pct:.2f}% "
            f"(threshold: {threshold_pct:.0f}%)"
        ),
        severity=_severity_for(margin_pct),
        fields={
            "Type": alert_type,
            "Margin": f"{margin_pct:.2f}% (threshold {threshold_pct:.0f}%)",
            "COGS": f"{cogs:.3f} TND",
            "Price": f"{price:.3f} TND",
            "Time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        },
    )


def _log_only(alert: Alert) -> None:
    """Render the alert to logs + stdout as the fallback delivery channel."""
    lines = [f"{alert.title}", alert.body]
    lines += [f"{k}: {v}" for k, v in alert.fields.items()]
    banner = "\n".join(lines)
    logger.warning("[ALERT] %s", banner)
    print(f"\n{'=' * 60}\n{banner}\n{'=' * 60}\n")


def send_slack_alert(
    webhook_url: Optional[str],
    product_name: str,
    alert_type: str,
    margin_pct: float,
    threshold_pct: float,
    cogs: float,
    price: float,
) -> bool:
    """Send a Slack alert via astk's SlackNotifier.

    Parameters
    ----------
    webhook_url : str or None
        The Slack incoming webhook URL. If None or empty, the alert is logged
        instead of sent.
    product_name : str
    alert_type : str
        'B2B' or 'B2C'.
    margin_pct : float
    threshold_pct : float
    cogs : float
    price : float

    Returns
    -------
    bool — True if the alert was delivered or logged (the pipeline should carry
    on either way); this function never raises.
    """
    alert = _build_alert(
        product_name, alert_type, margin_pct, threshold_pct, cogs, price
    )

    if not webhook_url:
        logger.warning("[ALERT] No Slack webhook configured — logging only.")
        _log_only(alert)
        return True

    try:
        result = SlackNotifier(webhook_url).send(alert)
    except Exception as exc:  # e.g. a malformed webhook_url — never break the pipeline
        logger.error("[ALERT] Slack notifier error: %s — logging instead", exc)
        _log_only(alert)
        return True

    if result.ok:
        logger.info(
            "[ALERT] Slack alert sent for %s (%s) in %d attempt(s)",
            product_name,
            alert_type,
            result.attempts,
        )
        return True

    logger.error(
        "[ALERT] Slack delivery failed after %d attempt(s): %s — logging instead",
        result.attempts,
        result.error,
    )
    _log_only(alert)
    return True


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
