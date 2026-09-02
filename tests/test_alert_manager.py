"""Unit tests for the alert manager.

Alerting is delegated to ``astk.alerts`` (shared toolkit): ``send_slack_alert``
builds an ``astk.alerts.Alert`` and posts it via ``astk.alerts.SlackNotifier``,
which retries on 429/5xx with backoff and never raises into the caller. These
tests exercise the adapter, not astk's own retry logic (that is tested in astk).

Note: these tests (and ``src.alert_manager`` itself) need the private
``analytics-service-toolkit`` (``astk``) installed. The lightweight CI install
does not have it, so the entire module skips gracefully via
``pytest.importorskip`` rather than failing collection — same pattern as
``test_api.py`` for fastapi.
"""
from unittest.mock import patch, MagicMock

import pytest

# Skip the whole module if astk isn't importable (lightweight CI install).
pytest.importorskip("astk")

from astk.alerts import AlertResult

from src.alert_manager import send_slack_alert, format_alert_message


class TestFormatAlertMessage:
    def test_format_b2c_alert(self):
        msg = format_alert_message("Test Oil", "B2C", 25.5, 40)
        assert "B2C" in msg
        assert "Test Oil" in msg
        assert "25.50%" in msg
        assert "40%" in msg

    def test_format_b2b_alert(self):
        msg = format_alert_message("Crème Hydratante", "B2B", 15.0, 30)
        assert "B2B" in msg
        assert "Crème Hydratante" in msg
        assert "15.00%" in msg


class TestSendSlackAlert:
    def test_no_webhook_logs_only(self):
        """When webhook_url is None, alert is logged but not sent."""
        result = send_slack_alert(
            webhook_url=None,
            product_name="Test Product",
            alert_type="B2C",
            margin_pct=25.0,
            threshold_pct=40.0,
            cogs=20.0,
            price=30.0,
        )
        assert result is True  # Returns True (logged)

    def test_empty_webhook_logs_only(self):
        """When webhook_url is empty string, alert is logged."""
        result = send_slack_alert(
            webhook_url="",
            product_name="Test Product",
            alert_type="B2B",
            margin_pct=15.0,
            threshold_pct=40.0,
            cogs=25.0,
            price=35.0,
        )
        assert result is True

    @patch("src.alert_manager.SlackNotifier")
    def test_successful_slack_send(self, mock_notifier_cls):
        """When webhook is configured, alert is sent via astk's SlackNotifier."""
        mock_notifier = MagicMock()
        mock_notifier.send.return_value = AlertResult(ok=True, attempts=1)
        mock_notifier_cls.return_value = mock_notifier

        result = send_slack_alert(
            webhook_url="https://hooks.slack.com/services/test",
            product_name="Test Product",
            alert_type="B2C",
            margin_pct=25.0,
            threshold_pct=40.0,
            cogs=20.0,
            price=30.0,
        )
        assert result is True
        mock_notifier_cls.assert_called_once_with("https://hooks.slack.com/services/test")
        mock_notifier.send.assert_called_once()
        # The alert built from the margin data carries the product name and type.
        sent_alert = mock_notifier.send.call_args.args[0]
        assert "Test Product" in sent_alert.title
        assert sent_alert.fields["Type"] == "B2C"

    @patch("src.alert_manager.SlackNotifier")
    def test_failed_send_falls_back_to_logging(self, mock_notifier_cls):
        """When astk reports a failed delivery, the alert is still logged (returns True)."""
        mock_notifier = MagicMock()
        mock_notifier.send.return_value = AlertResult(ok=False, attempts=3, error="HTTP 500")
        mock_notifier_cls.return_value = mock_notifier

        result = send_slack_alert(
            webhook_url="https://hooks.slack.com/services/test",
            product_name="Test Product",
            alert_type="B2C",
            margin_pct=25.0,
            threshold_pct=40.0,
            cogs=20.0,
            price=30.0,
        )
        assert result is True  # Falls back to logging
        mock_notifier.send.assert_called_once()

    @patch("src.alert_manager.SlackNotifier")
    def test_notifier_construction_error_never_breaks_pipeline(self, mock_notifier_cls):
        """A bad webhook (astk raises ValueError on construction) must not raise."""
        mock_notifier_cls.side_effect = ValueError("webhook_url must be an http:// or https:// URL")

        result = send_slack_alert(
            webhook_url="not-a-url",
            product_name="Test Product",
            alert_type="B2C",
            margin_pct=25.0,
            threshold_pct=40.0,
            cogs=20.0,
            price=30.0,
        )
        assert result is True  # Logged fallback; never propagates

    @patch("src.alert_manager.SlackNotifier")
    def test_negative_margin_is_critical(self, mock_notifier_cls):
        """Selling below cost (negative margin) is a critical alert, not a warning."""
        mock_notifier = MagicMock()
        mock_notifier.send.return_value = AlertResult(ok=True, attempts=1)
        mock_notifier_cls.return_value = mock_notifier

        send_slack_alert(
            webhook_url="https://hooks.slack.com/services/test",
            product_name="Loss Leader",
            alert_type="B2B",
            margin_pct=-5.0,
            threshold_pct=30.0,
            cogs=42.0,
            price=40.0,
        )
        sent_alert = mock_notifier.send.call_args.args[0]
        assert sent_alert.severity == "critical"
