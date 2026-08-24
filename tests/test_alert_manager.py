"""Unit tests for the alert manager."""
from unittest.mock import patch, MagicMock
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

    @patch("src.alert_manager.urlopen")
    def test_successful_slack_send(self, mock_urlopen):
        """When webhook is configured, alert is sent via HTTP."""
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

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
        mock_urlopen.assert_called_once()

    @patch("src.alert_manager.urlopen")
    def test_slack_non_200_response_returns_false(self, mock_urlopen):
        """When Slack responds but not with 200, the call is treated as failed
        (unlike a raised exception, this path does NOT fall back to logging)."""
        mock_resp = MagicMock()
        mock_resp.status = 429
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = send_slack_alert(
            webhook_url="https://hooks.slack.com/services/test",
            product_name="Test Product",
            alert_type="B2C",
            margin_pct=25.0,
            threshold_pct=40.0,
            cogs=20.0,
            price=30.0,
        )
        assert result is False
        mock_urlopen.assert_called_once()

    @patch("src.alert_manager.urlopen")
    def test_slack_error_falls_back_to_logging(self, mock_urlopen):
        """When Slack returns an error, alert is still logged."""
        mock_urlopen.side_effect = Exception("Network error")

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
