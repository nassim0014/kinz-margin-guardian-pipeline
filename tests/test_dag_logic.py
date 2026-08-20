"""Tests for src/dag_logic.py — extracted Airflow DAG logic (item 3).

Tests the pure-logic functions extracted from margin_guardian_dag.py:
get_execution_date, validate_price_data, build_margin_records, build_alert_data.
No database or Airflow dependencies needed.
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from src.dag_logic import (
    build_alert_data,
    build_margin_records,
    get_execution_date,
    validate_price_data,
)


class TestGetExecutionDate:
    def test_extracts_from_ds(self):
        """context['ds'] is parsed as YYYY-MM-DD."""
        assert get_execution_date({"ds": "2026-08-20"}) == date(2026, 8, 20)

    def test_falls_back_to_today_when_no_ds(self):
        """Without 'ds', returns date.today()."""
        result = get_execution_date({})
        assert result == date.today()

    def test_falls_back_to_today_when_ds_none(self):
        """When 'ds' is None, returns date.today()."""
        result = get_execution_date({"ds": None})
        assert result == date.today()


class TestValidatePriceData:
    def test_valid_data_returns_true(self):
        prices = pd.DataFrame({"product_id": [1, 2], "competitor_price_tnd": [40.0, 50.0]})
        products = pd.DataFrame({"id": [1, 2], "name": ["A", "B"], "cogs_tnd": [20.0, 25.0]})
        is_valid, reason = validate_price_data(prices, products)
        assert is_valid is True
        assert reason == ""

    def test_empty_prices_returns_false(self):
        prices = pd.DataFrame({"product_id": [], "competitor_price_tnd": []})
        products = pd.DataFrame({"id": [1], "name": ["A"], "cogs_tnd": [20.0]})
        is_valid, reason = validate_price_data(prices, products)
        assert is_valid is False
        assert "No prices" in reason

    def test_zero_price_returns_false(self):
        prices = pd.DataFrame({"product_id": [1], "competitor_price_tnd": [0.0]})
        products = pd.DataFrame({"id": [1], "name": ["A"], "cogs_tnd": [20.0]})
        is_valid, reason = validate_price_data(prices, products)
        assert is_valid is False
        assert "<= 0" in reason
        assert "[1]" in reason

    def test_negative_price_returns_false(self):
        prices = pd.DataFrame({"product_id": [1, 2], "competitor_price_tnd": [40.0, -5.0]})
        products = pd.DataFrame({"id": [1, 2], "name": ["A", "B"], "cogs_tnd": [20.0, 25.0]})
        is_valid, reason = validate_price_data(prices, products)
        assert is_valid is False
        assert "<= 0" in reason
        assert "[2]" in reason

    def test_zero_cogs_returns_false(self):
        prices = pd.DataFrame({"product_id": [1], "competitor_price_tnd": [40.0]})
        products = pd.DataFrame({"id": [1], "name": ["A"], "cogs_tnd": [0.0]})
        is_valid, reason = validate_price_data(prices, products)
        assert is_valid is False
        assert "COGS" in reason
        assert "['A']" in reason

    def test_empty_products_returns_false(self):
        prices = pd.DataFrame({"product_id": [1], "competitor_price_tnd": [40.0]})
        products = pd.DataFrame({"id": [], "name": [], "cogs_tnd": []})
        is_valid, reason = validate_price_data(prices, products)
        assert is_valid is False
        assert "No products" in reason


class TestBuildMarginRecords:
    def test_empty_rows_returns_empty_list(self):
        assert build_margin_records([], date(2026, 8, 20)) == []

    def test_single_row_builds_record(self):
        """A single row produces one margin record with calculated margins."""
        rows = [(1, "Product A", 20.0, 40.0, 45.0, date(2026, 8, 20))]
        records = build_margin_records(rows, date(2026, 8, 20))
        assert len(records) == 1
        rec = records[0]
        assert rec["product_id"] == 1
        assert rec["cogs_tnd"] == 20.0
        # b2c_price = competitor_price = 45.0
        assert rec["b2c_price_tnd"] == 45.0
        # b2c_margin = (45-20)/45*100 = 55.56 (rounded to 2dp)
        assert rec["b2c_margin_pct"] == 55.56
        assert rec["calc_date"] == date(2026, 8, 20)

    def test_uses_exec_date_when_row_has_no_price_date(self):
        """When the row has fewer than 6 elements, exec_date is used."""
        rows = [(1, "A", 20.0, 40.0, 45.0)]  # no price_date
        records = build_margin_records(rows, date(2026, 8, 20))
        assert records[0]["calc_date"] == date(2026, 8, 20)

    def test_uses_row_price_date_when_present(self):
        """When the row has a price_date, it overrides exec_date."""
        rows = [(1, "A", 20.0, 40.0, 45.0, date(2026, 8, 19))]
        records = build_margin_records(rows, date(2026, 8, 20))
        assert records[0]["calc_date"] == date(2026, 8, 19)

    def test_multiple_rows(self):
        rows = [
            (1, "A", 20.0, 40.0, 40.0, date(2026, 8, 20)),
            (2, "B", 15.0, 40.0, 30.0, date(2026, 8, 20)),
        ]
        records = build_margin_records(rows, date(2026, 8, 20))
        assert len(records) == 2
        assert records[0]["product_id"] == 1
        assert records[1]["product_id"] == 2


class TestBuildAlertData:
    def test_empty_rows_returns_empty_list(self):
        assert build_alert_data([]) == []

    def test_no_alerts_when_margins_above_threshold(self):
        """Margins above threshold produce no alerts."""
        # margin = (40-20)/40*100 = 50% > 40%
        rows = [(1, "A", 50.0, 42.5, 40.0, 20.0, 40.0, 34.0)]
        alerts = build_alert_data(rows)
        assert alerts == []

    def test_b2c_alert_when_margin_below_threshold(self):
        """B2C margin below threshold produces a B2C alert (B2B above threshold)."""
        # B2C margin = (40-35)/40*100 = 12.5% < 40%
        # B2B margin = (34-35)/34*100 = -2.94% < 40% → also alerts
        # To test B2C-only, set B2B margin above threshold:
        rows = [(1, "Product A", 12.5, 50.0, 40.0, 35.0, 40.0, 34.0)]
        alerts = build_alert_data(rows)
        assert len(alerts) == 1
        assert alerts[0]["alert_type"] == "B2C"
        assert alerts[0]["product_name"] == "Product A"
        assert alerts[0]["margin_pct"] == 12.5
        assert alerts[0]["threshold_pct"] == 40.0
        assert "Product A" in alerts[0]["message"]

    def test_b2b_alert_when_margin_below_threshold(self):
        """B2B margin below threshold produces a B2B alert."""
        # B2B price = 40 * 0.85 = 34, margin = (34-35)/34*100 = -2.94% < 40%
        rows = [(1, "A", 12.5, -2.94, 40.0, 35.0, 40.0, 34.0)]
        alerts = build_alert_data(rows)
        assert len(alerts) == 2  # both B2C and B2B below threshold
        b2b = next(a for a in alerts if a["alert_type"] == "B2B")
        assert b2b["price"] == 34.0

    def test_both_alerts_for_one_product(self):
        """When both margins are below threshold, two alerts are created."""
        rows = [(1, "A", 10.0, 5.0, 40.0, 35.0, 40.0, 34.0)]
        alerts = build_alert_data(rows)
        assert len(alerts) == 2
        types = {a["alert_type"] for a in alerts}
        assert types == {"B2C", "B2B"}

    def test_uses_default_threshold_when_null(self):
        """When threshold is None, DEFAULT_ALERT_THRESHOLD_PCT (40) is used."""
        # B2C = 30% < 40% default → alert. B2B = 50% > 40% → no alert.
        rows = [(1, "A", 30.0, 50.0, None, 35.0, 40.0, 34.0)]
        alerts = build_alert_data(rows)
        assert len(alerts) == 1
        assert alerts[0]["threshold_pct"] == 40.0
