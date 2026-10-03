"""Tests for the offline demo CLI (scripts/demo.py).

No database, no Docker, no astk required -- that is the whole point of the demo,
so these tests exercise it exactly the way CI runs: against the plain function
imports, with no fixtures standing up Postgres.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.demo import DEMO_PRODUCTS, render_alert_lines, render_table, run_demo


class TestRunDemo:
    def test_returns_one_result_per_product(self):
        results = run_demo(seed=42)
        assert len(results) == len(DEMO_PRODUCTS) == 5

    def test_product_names_match_catalogue(self):
        results = run_demo(seed=42)
        assert [r.product_name for r in results] == [p.name for p in DEMO_PRODUCTS]

    def test_deterministic_given_same_seed(self):
        first = run_demo(seed=42)
        second = run_demo(seed=42)
        assert [r.b2c_margin_pct for r in first] == [r.b2c_margin_pct for r in second]
        assert [r.competitor_price_tnd for r in first] == [r.competitor_price_tnd for r in second]

    def test_different_seeds_can_change_prices(self):
        a = run_demo(seed=1)
        b = run_demo(seed=2)
        assert [r.competitor_price_tnd for r in a] != [r.competitor_price_tnd for r in b]

    def test_at_least_one_alert_with_default_seed(self):
        """The catalogue deliberately prices one product under the 40% threshold."""
        results = run_demo(seed=42)
        assert any(r.b2c_alert or r.b2b_alert for r in results)

    def test_margins_match_margin_engine_formula(self):
        """Spot-check one product's numbers against the real margin_engine formula,
        not a hardcoded expected value, so this stays correct if the noise model
        or seed ever changes."""
        from src.margin_engine import calculate_margins

        results = run_demo(seed=42)
        product = DEMO_PRODUCTS[0]
        result = results[0]
        _, _, expected_b2c, expected_b2b = calculate_margins(
            product.cogs_tnd, result.competitor_price_tnd
        )
        assert result.b2c_margin_pct == expected_b2c
        assert result.b2b_margin_pct == expected_b2b


class TestRenderTable:
    def test_table_has_one_row_per_product(self):
        results = run_demo(seed=42)
        table = render_table(results)
        lines = table.strip().splitlines()
        # header + separator + 5 product rows
        assert len(lines) == 2 + len(results)
        for product in DEMO_PRODUCTS:
            assert product.name in table

    def test_alert_marker_appears_for_alerting_product(self):
        results = run_demo(seed=42)
        table = render_table(results)
        alerting_names = [r.product_name for r in results if r.b2c_alert or r.b2b_alert]
        assert alerting_names, "expected at least one alerting product at seed=42"
        for name in alerting_names:
            row = next(line for line in table.splitlines() if line.startswith(name))
            assert "ALERT" in row


class TestRenderAlertLines:
    def test_no_astk_import_required(self):
        """format_alert_message is the pure helper documented as safe without the
        private astk package -- this must not raise even when astk isn't installed
        (the lightweight CI / this sandbox)."""
        results = run_demo(seed=42)
        lines = render_alert_lines(results)
        assert lines
        assert any("B2C" in line or "B2B" in line for line in lines)

    def test_no_lines_when_nothing_alerts(self):
        results = run_demo(seed=42)
        for r in results:
            r.b2c_alert = False
            r.b2b_alert = False
        assert render_alert_lines(results) == []


class TestJsonOutput:
    def test_json_schema_and_count(self, tmp_path):
        from scripts.demo import main

        out = tmp_path / "demo.json"
        rc = main(["--seed", "42", "--json", str(out)])
        assert rc == 0

        data = json.loads(out.read_text())
        assert len(data) == 5
        required_keys = {
            "product_name", "b2c_margin_pct", "b2b_margin_pct", "b2c_alert", "b2b_alert",
        }
        for entry in data:
            assert required_keys.issubset(entry.keys())
