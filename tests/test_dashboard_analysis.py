"""Tests for dashboard/analysis.py — extracted pure computation (item 4).

These cover the What-If Simulator's adjustment math, the scenario summary
builder, and the delta formatter. No Streamlit or database needed.
"""
from __future__ import annotations

import pandas as pd

from dashboard.analysis import build_scenario_summary, compute_adjusted_values, fmt_delta


class TestComputeAdjustedValues:
    def test_no_adjustment(self):
        """0% adjustment returns the original values (rounded to 3 dp)."""
        cogs, price = compute_adjusted_values(20.0, 40.0, 0, 0)
        assert cogs == 20.0
        assert price == 40.0

    def test_positive_adjustment(self):
        """+10% COGS, +20% price."""
        cogs, price = compute_adjusted_values(20.0, 40.0, 10, 20)
        assert cogs == 22.0
        assert price == 48.0

    def test_negative_adjustment(self):
        """-15% COGS, -25% price."""
        cogs, price = compute_adjusted_values(20.0, 40.0, -15, -25)
        assert cogs == 17.0
        assert price == 30.0

    def test_rounding_to_3dp(self):
        """Values are rounded to 3 decimal places."""
        cogs, price = compute_adjusted_values(33.3333, 66.6666, 1, 1)
        assert cogs == round(33.3333 * 1.01, 3)
        assert price == round(66.6666 * 1.01, 3)

    def test_zero_cogs(self):
        """Zero COGS stays zero."""
        cogs, _ = compute_adjusted_values(0.0, 40.0, 10, 0)
        assert cogs == 0.0


class TestFmtDelta:
    def test_positive_delta(self):
        assert fmt_delta(5.0) == "+5.00"

    def test_negative_delta(self):
        assert fmt_delta(-3.5) == "-3.50"

    def test_zero_delta(self):
        """Zero is formatted with a + sign (per the original code)."""
        assert fmt_delta(0.0) == "+0.00"

    def test_percent_suffix(self):
        assert fmt_delta(2.5, is_pct=True) == "+2.50%"

    def test_negative_percent(self):
        assert fmt_delta(-1.5, is_pct=True) == "-1.50%"


class TestBuildScenarioSummary:
    def test_returns_dataframe(self):
        """The summary is a DataFrame with the expected columns."""
        df = build_scenario_summary(
            current_cogs=20.0, adjusted_cogs=22.0,
            current_price=40.0, adjusted_price=48.0,
            threshold=40.0,
        )
        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == ["Metric", "Original", "Adjusted", "Delta"]

    def test_has_seven_rows(self):
        """The summary has 7 metric rows: COGS, B2C Price, B2B Price, B2C Margin, B2B Margin, B2C Alert, B2B Alert."""
        df = build_scenario_summary(20.0, 20.0, 40.0, 40.0, 40.0)
        assert len(df) == 7

    def test_no_change_scenario(self):
        """When adjusted == current, the numeric deltas are +0.00."""
        df = build_scenario_summary(
            current_cogs=20.0, adjusted_cogs=20.0,
            current_price=40.0, adjusted_price=40.0,
            threshold=40.0,
        )
        # The first 5 rows (COGS, B2C Price, B2B Price, B2C Margin, B2B Margin)
        # are numeric deltas; the last 2 (B2C Alert, B2B Alert) use "—".
        numeric_deltas = df["Delta"].iloc[:5]
        for delta in numeric_deltas:
            assert "0.00" in delta
        # The alert rows use "—" (no delta concept for a boolean)
        assert df["Delta"].iloc[5] == "—"
        assert df["Delta"].iloc[6] == "—"

    def test_alert_when_margin_below_threshold(self):
        """When margin < threshold, the Adjusted alert column shows 🚨 Yes."""
        # COGS=35, price=40 → margin = (40-35)/40*100 = 12.5% < 40%
        df = build_scenario_summary(
            current_cogs=35.0, adjusted_cogs=35.0,
            current_price=40.0, adjusted_price=40.0,
            threshold=40.0,
        )
        b2c_alert_row = df[df["Metric"] == "B2C Alert"].iloc[0]
        assert "🚨 Yes" in b2c_alert_row["Adjusted"]

    def test_no_alert_when_margin_above_threshold(self):
        """When margin > threshold, the Adjusted alert column shows ✅ No."""
        # COGS=10, price=40 → margin = (40-10)/40*100 = 75% > 40%
        df = build_scenario_summary(
            current_cogs=10.0, adjusted_cogs=10.0,
            current_price=40.0, adjusted_price=40.0,
            threshold=40.0,
        )
        b2c_alert_row = df[df["Metric"] == "B2C Alert"].iloc[0]
        assert "✅ No" in b2c_alert_row["Adjusted"]

    def test_cogs_increase_lowers_margin(self):
        """Raising COGS while keeping price fixed should lower the margin."""
        df_no_change = build_scenario_summary(20.0, 20.0, 40.0, 40.0, 40.0)
        df_cogs_up = build_scenario_summary(20.0, 25.0, 40.0, 40.0, 40.0)

        margin_no_change = float(df_no_change[df_no_change["Metric"] == "B2C Margin (%)"].iloc[0]["Adjusted"])
        margin_cogs_up = float(df_cogs_up[df_cogs_up["Metric"] == "B2C Margin (%)"].iloc[0]["Adjusted"])
        assert margin_cogs_up < margin_no_change

    def test_price_increase_raises_margin(self):
        """Raising price while keeping COGS fixed should raise the margin."""
        df_no_change = build_scenario_summary(20.0, 20.0, 40.0, 40.0, 40.0)
        df_price_up = build_scenario_summary(20.0, 20.0, 40.0, 50.0, 40.0)

        margin_no_change = float(df_no_change[df_no_change["Metric"] == "B2C Margin (%)"].iloc[0]["Adjusted"])
        margin_price_up = float(df_price_up[df_price_up["Metric"] == "B2C Margin (%)"].iloc[0]["Adjusted"])
        assert margin_price_up > margin_no_change
