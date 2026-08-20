"""Pure computation extracted from dashboard/app.py (item 4).

These functions are the testable parts of the What-If Simulator tab —
the adjustment math, the scenario summary builder, and the delta
formatter. They have no Streamlit or database dependencies, so they
can be unit-tested without running the dashboard.

Pattern: dashboard/app.py imports these and calls them inside its
`st.*` blocks, leaving only presentation code in app.py.
"""
from __future__ import annotations

import pandas as pd

from src.config import B2B_DISCOUNT_FACTOR
from src.margin_engine import calculate_margins, check_margin_threshold


def compute_adjusted_values(
    current_cogs: float,
    current_price: float,
    cogs_adjust_pct: float,
    price_adjust_pct: float,
) -> tuple[float, float]:
    """Apply percentage adjustments to COGS and competitor price.

    Args:
        current_cogs: Current COGS in TND.
        current_price: Current competitor/B2C price in TND.
        cogs_adjust_pct: COGS adjustment in percent (e.g. -5 for -5%).
        price_adjust_pct: Price adjustment in percent.

    Returns:
        (adjusted_cogs, adjusted_price) rounded to 3 decimal places.
    """
    adjusted_cogs = round(current_cogs * (1 + cogs_adjust_pct / 100), 3)
    adjusted_price = round(current_price * (1 + price_adjust_pct / 100), 3)
    return adjusted_cogs, adjusted_price


def build_scenario_summary(
    current_cogs: float,
    adjusted_cogs: float,
    current_price: float,
    adjusted_price: float,
    threshold: float,
    b2b_discount: float = B2B_DISCOUNT_FACTOR,
) -> pd.DataFrame:
    """Build the What-If scenario summary table.

    Computes original + adjusted margins, alert states, and deltas,
    returning a DataFrame suitable for `st.table()`.

    Args:
        current_cogs: Original COGS in TND.
        adjusted_cogs: Adjusted COGS in TND.
        current_price: Original competitor price in TND.
        adjusted_price: Adjusted competitor price in TND.
        threshold: Alert threshold percentage (e.g. 40.0).
        b2b_discount: B2B discount factor (default from config).

    Returns:
        DataFrame with columns: Metric, Original, Adjusted, Delta.
    """
    # Original margins
    b2c_price_orig, b2b_price_orig, b2c_margin_orig, b2b_margin_orig = calculate_margins(
        current_cogs, current_price, b2b_discount
    )
    # Adjusted margins
    b2c_price_new, b2b_price_new, b2c_margin_new, b2b_margin_new = calculate_margins(
        adjusted_cogs, adjusted_price, b2b_discount
    )
    # Alerts
    b2c_alert_new, b2b_alert_new = check_margin_threshold(
        b2c_margin_new, b2b_margin_new, threshold
    )

    def fmt_delta(delta: float, is_pct: bool = False) -> str:
        suffix = "%" if is_pct else ""
        sign = "+" if delta >= 0 else ""
        return f"{sign}{delta:.2f}{suffix}"

    return pd.DataFrame([
        {"Metric": "COGS (TND)", "Original": f"{current_cogs:.3f}",
         "Adjusted": f"{adjusted_cogs:.3f}",
         "Delta": fmt_delta(adjusted_cogs - current_cogs)},
        {"Metric": "B2C Price (TND)", "Original": f"{b2c_price_orig:.3f}",
         "Adjusted": f"{b2c_price_new:.3f}",
         "Delta": fmt_delta(b2c_price_new - b2c_price_orig)},
        {"Metric": "B2B Price (TND)", "Original": f"{b2b_price_orig:.3f}",
         "Adjusted": f"{b2b_price_new:.3f}",
         "Delta": fmt_delta(b2b_price_new - b2b_price_orig)},
        {"Metric": "B2C Margin (%)", "Original": f"{b2c_margin_orig:.2f}",
         "Adjusted": f"{b2c_margin_new:.2f}",
         "Delta": fmt_delta(b2c_margin_new - b2c_margin_orig, is_pct=True)},
        {"Metric": "B2B Margin (%)", "Original": f"{b2b_margin_orig:.2f}",
         "Adjusted": f"{b2b_margin_new:.2f}",
         "Delta": fmt_delta(b2b_margin_new - b2b_margin_orig, is_pct=True)},
        {"Metric": "B2C Alert", "Original": "🚨 Yes" if b2c_margin_orig < threshold else "✅ No",
         "Adjusted": "🚨 Yes" if b2c_alert_new else "✅ No", "Delta": "—"},
        {"Metric": "B2B Alert", "Original": "🚨 Yes" if b2b_margin_orig < threshold else "✅ No",
         "Adjusted": "🚨 Yes" if b2b_alert_new else "✅ No", "Delta": "—"},
    ])


def fmt_delta(delta: float, is_pct: bool = False) -> str:
    """Format a delta value with sign and optional percent suffix.

    Args:
        delta: The numeric delta (positive or negative).
        is_pct: If True, append "%" suffix.

    Returns:
        Formatted string like "+1.50%" or "-2.30".
    """
    suffix = "%" if is_pct else ""
    sign = "+" if delta >= 0 else ""
    return f"{sign}{delta:.2f}{suffix}"
