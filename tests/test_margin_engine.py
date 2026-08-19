"""Unit tests for the margin calculation engine."""

from src.margin_engine import (
    calculate_margins,
    check_margin_threshold,
    compute_product_margins,
    MarginResult,
)
from src.config import B2B_DISCOUNT_FACTOR


class TestCalculateMargins:
    def test_positive_margins(self):
        """Normal case: price > COGS → positive margins."""
        b2c, b2b, b2c_m, b2b_m = calculate_margins(cogs=20, competitor_price=50)
        assert b2c == 50.0
        assert b2b == 50.0 * B2B_DISCOUNT_FACTOR
        assert b2c_m == 60.0  # (50-20)/50 = 60%
        assert b2b_m == round((50 * 0.85 - 20) / (50 * 0.85) * 100, 2)

    def test_zero_margin(self):
        """Price = COGS → 0% margin."""
        _, _, b2c_m, b2b_m = calculate_margins(cogs=30, competitor_price=30)
        assert b2c_m == 0.0
        assert b2b_m < 0  # B2B price is lower (×0.85), so margin is negative

    def test_negative_margin(self):
        """Price < COGS → negative margins."""
        _, _, b2c_m, b2b_m = calculate_margins(cogs=50, competitor_price=30)
        assert b2c_m < 0
        assert b2b_m < 0

    def test_zero_price(self):
        """Price = 0 → margins should be 0 (not division by zero)."""
        _, _, b2c_m, b2b_m = calculate_margins(cogs=20, competitor_price=0)
        assert b2c_m == 0.0
        assert b2b_m == 0.0

    def test_b2b_lower_than_b2c(self):
        """B2B margin should always be lower than B2C (due to 15% discount)."""
        _, _, b2c_m, b2b_m = calculate_margins(cogs=10, competitor_price=40)
        assert b2b_m < b2c_m


class TestCheckMarginThreshold:
    def test_both_above_threshold(self):
        """Both margins above threshold → no alerts."""
        b2c_alert, b2b_alert = check_margin_threshold(60, 50, threshold_pct=40)
        assert b2c_alert is False
        assert b2b_alert is False

    def test_both_below_threshold(self):
        """Both margins below threshold → both alert."""
        b2c_alert, b2b_alert = check_margin_threshold(30, 25, threshold_pct=40)
        assert b2c_alert is True
        assert b2b_alert is True

    def test_b2b_only_below(self):
        """B2C above, B2B below → only B2B alerts."""
        b2c_alert, b2b_alert = check_margin_threshold(45, 35, threshold_pct=40)
        assert b2c_alert is False
        assert b2b_alert is True

    def test_default_threshold(self):
        """Default threshold is 40%."""
        b2c_alert, _ = check_margin_threshold(39, 50)
        assert b2c_alert is True  # 39 < 40 default


class TestComputeProductMargins:
    def test_returns_margin_result(self):
        """compute_product_margins returns a MarginResult dataclass."""
        result = compute_product_margins(
            product_id=1, product_name="Test Oil",
            cogs=20, competitor_price=50, threshold_pct=40,
        )
        assert isinstance(result, MarginResult)
        assert result.product_id == 1
        assert result.product_name == "Test Oil"
        assert result.b2c_margin_pct == 60.0
        assert result.b2c_alert is False
        assert result.b2b_alert is False

    def test_alert_triggered(self):
        """Alert triggered when margin < threshold."""
        result = compute_product_margins(
            product_id=2, product_name="Low Margin Product",
            cogs=45, competitor_price=50, threshold_pct=40,
        )
        assert result.b2c_margin_pct == 10.0
        assert result.b2c_alert is True
