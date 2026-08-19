"""
Kinz Margin Guardian — Streamlit Dashboard

Interactive dashboard for visualizing KINZ product margins, alert history,
and a What-If margin simulator for business stakeholders.

Pages (tabs):
  1. 📊 Dashboard — margin health gauges, erosion timeline, alert log
  2. 🔮 What-If Simulator — interactive COGS/price sliders with live margin recalculation
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
from sqlalchemy import create_engine, text

# ---------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------
st.set_page_config(
    page_title="Kinz Margin Guardian",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import DATABASE_URL  # noqa: E402
from src.margin_engine import calculate_margins, check_margin_threshold  # noqa: E402
from src.config import B2B_DISCOUNT_FACTOR  # noqa: E402


@st.cache_resource
def get_engine():
    return create_engine(DATABASE_URL)


@st.cache_data(ttl=60)
def load_products() -> pd.DataFrame:
    """Load all active products."""
    engine = get_engine()
    return pd.read_sql(text("SELECT * FROM products WHERE active = true ORDER BY name"), engine)


@st.cache_data(ttl=60)
def load_margin_history() -> pd.DataFrame:
    """Load all margin history."""
    engine = get_engine()
    return pd.read_sql(text("""
        SELECT mh.*, p.name as product_name, p.category
        FROM margin_history mh
        JOIN products p ON mh.product_id = p.id
        ORDER BY mh.calc_date DESC
    """), engine)


@st.cache_data(ttl=60)
def load_alerts(limit: int = 100) -> pd.DataFrame:
    """Load recent alerts."""
    engine = get_engine()
    return pd.read_sql(text("""
        SELECT a.*, p.name as product_name
        FROM alerts a
        JOIN products p ON a.product_id = p.id
        ORDER BY a.alert_date DESC
        LIMIT :limit
    """), engine, params={"limit": limit})


@st.cache_data(ttl=60)
def load_daily_prices() -> pd.DataFrame:
    """Load daily prices for trend visualization."""
    engine = get_engine()
    return pd.read_sql(text("""
        SELECT dp.*, p.name as product_name
        FROM daily_prices dp
        JOIN products p ON dp.product_id = p.id
        ORDER BY dp.price_date DESC
    """), engine)


# ---------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------
st.title("🛡️ Kinz Margin Guardian")
st.markdown("Real-time B2B + B2C margin monitoring with automated alerting for KINZ products.")

# ---------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------
try:
    products_df = load_products()
    margins_df = load_margin_history()
    alerts_df = load_alerts()
    prices_df = load_daily_prices()
except Exception as e:
    st.error(f"⚠️ Could not connect to the database: {e}")
    st.info("Make sure Docker Compose is running (`docker compose up -d`) and the database is seeded (`make seed`).")
    st.stop()

# ---------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------
tab_dashboard, tab_whatif = st.tabs(["📊 Dashboard", "🔮 What-If Simulator"])

# ============================================================
# Tab 1: Dashboard
# ============================================================
with tab_dashboard:
    st.subheader("📊 Margin Health Overview")

    if margins_df.empty:
        st.warning("No margin data available yet. Run the Airflow DAG to calculate margins.")
    else:
        # --- KPI metrics at the top ---
        col1, col2, col3, col4 = st.columns(4)

        latest_date = margins_df["calc_date"].max()
        latest_margins = margins_df[margins_df["calc_date"] == latest_date]

        col1.metric("Products Tracked", len(products_df))
        col2.metric("Latest Calculation", str(latest_date))
        col3.metric("Avg B2C Margin", f"{latest_margins['b2c_margin_pct'].mean():.1f}%")
        col4.metric("Active Alerts", len(alerts_df))

        # --- Product selector for gauge ---
        st.markdown("---")
        col_gauge, col_trend = st.columns([1, 2])

        with col_gauge:
            st.markdown("#### Margin Health Gauge")
            selected_product = st.selectbox(
                "Select product:",
                options=products_df["name"].tolist(),
                key="gauge_product",
            )

            prod_margins = latest_margins[latest_margins["product_id"].isin(
                products_df[products_df["name"] == selected_product]["id"]
            )]

            if not prod_margins.empty:
                row = prod_margins.iloc[0]
                b2c_margin = float(row["b2c_margin_pct"])
                b2b_margin = float(row["b2b_margin_pct"])
                threshold = float(products_df[products_df["name"] == selected_product]["alert_threshold_pct"].iloc[0])

                # B2C gauge
                fig_gauge = go.Figure()
                fig_gauge.add_trace(go.Indicator(
                    mode="gauge+number",
                    value=b2c_margin,
                    title={"text": f"B2C Margin — {selected_product[:30]}"},
                    gauge={
                        "axis": {"range": [-50, 80]},
                        "bar": {"color": "#00d4ff"},
                        "steps": [
                            {"range": [-50, threshold - 10], "color": "#dc2626"},
                            {"range": [threshold - 10, threshold], "color": "#f59e0b"},
                            {"range": [threshold, 80], "color": "#16a34a"},
                        ],
                        "threshold": {
                            "line": {"color": "white", "width": 3},
                            "thickness": 0.75,
                            "value": threshold,
                        },
                    },
                ))
                fig_gauge.update_layout(template="plotly_dark", height=300)
                st.plotly_chart(fig_gauge, use_container_width=True)

                # B2B gauge
                fig_gauge2 = go.Figure()
                fig_gauge2.add_trace(go.Indicator(
                    mode="gauge+number",
                    value=b2b_margin,
                    title={"text": f"B2B Margin — {selected_product[:30]}"},
                    gauge={
                        "axis": {"range": [-50, 80]},
                        "bar": {"color": "#f59e0b"},
                        "steps": [
                            {"range": [-50, threshold - 10], "color": "#dc2626"},
                            {"range": [threshold - 10, threshold], "color": "#f59e0b"},
                            {"range": [threshold, 80], "color": "#16a34a"},
                        ],
                        "threshold": {
                            "line": {"color": "white", "width": 3},
                            "thickness": 0.75,
                            "value": threshold,
                        },
                    },
                ))
                fig_gauge2.update_layout(template="plotly_dark", height=300)
                st.plotly_chart(fig_gauge2, use_container_width=True)
            else:
                st.info(f"No margin data for {selected_product} on {latest_date}.")

        with col_trend:
            st.markdown("#### Margin Erosion Timeline")

            # Trend for the selected product
            prod_id = products_df[products_df["name"] == selected_product]["id"].iloc[0]
            prod_history = margins_df[margins_df["product_id"] == prod_id].sort_values("calc_date")

            if not prod_history.empty:
                fig_trend = go.Figure()
                fig_trend.add_trace(go.Scatter(
                    x=prod_history["calc_date"], y=prod_history["b2c_margin_pct"],
                    mode="lines+markers", name="B2C Margin",
                    line=dict(color="#00d4ff", width=2),
                ))
                fig_trend.add_trace(go.Scatter(
                    x=prod_history["calc_date"], y=prod_history["b2b_margin_pct"],
                    mode="lines+markers", name="B2B Margin",
                    line=dict(color="#f59e0b", width=2),
                ))
                fig_trend.add_hline(y=threshold, line_dash="dash", line_color="red",
                                    annotation_text=f"Threshold ({threshold}%)")
                fig_trend.update_layout(
                    template="plotly_dark", height=350,
                    xaxis_title="Date", yaxis_title="Margin (%)",
                    hovermode="x unified",
                )
                st.plotly_chart(fig_trend, use_container_width=True)
            else:
                st.info("No historical data for this product yet.")

        # --- Product comparison bar chart ---
        st.markdown("---")
        st.markdown("#### Product Margin Comparison (Latest)")

        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(
            x=latest_margins["product_name"] if "product_name" in latest_margins.columns else
            [products_df[products_df["id"] == pid]["name"].iloc[0] for pid in latest_margins["product_id"]],
            y=latest_margins["b2c_margin_pct"],
            name="B2C Margin",
            marker_color=["#16a34a" if m >= threshold else "#dc2626" for m in latest_margins["b2c_margin_pct"]],
        ))
        fig_bar.update_layout(
            template="plotly_dark", height=400,
            xaxis_title="Product", yaxis_title="Margin (%)",
            xaxis_tickangle=-45, showlegend=False,
        )
        st.plotly_chart(fig_bar, use_container_width=True)

        # --- Alert log table ---
        st.markdown("---")
        st.markdown("#### 🚨 Alert Log")

        if not alerts_df.empty:
            display_alerts = alerts_df[["product_name", "alert_type", "margin_pct",
                                        "threshold_pct", "alert_date", "notified"]].copy()
            display_alerts.columns = ["Product", "Type", "Margin %", "Threshold %", "Date", "Notified"]
            st.dataframe(display_alerts, use_container_width=True, hide_index=True)
        else:
            st.success("✅ No alerts triggered — all margins are above threshold!")

        # --- COGS vs Price scatter ---
        st.markdown("---")
        st.markdown("#### COGS vs Price (bubble size = margin %)")

        if not latest_margins.empty:
            scatter_df = latest_margins.merge(
                products_df[["id", "name"]], left_on="product_id", right_on="id", suffixes=("", "_p")
            )
            fig_scatter = px.scatter(
                scatter_df,
                x="cogs_tnd",
                y="b2c_price_tnd",
                size="b2c_margin_pct",
                color="b2c_margin_pct",
                color_continuous_scale=["#dc2626", "#f59e0b", "#16a34a"],
                hover_name="name_p" if "name_p" in scatter_df.columns else "product_id",
                title="COGS vs B2C Price (bubble = margin %)",
                template="plotly_dark",
            )
            fig_scatter.update_layout(height=400)
            st.plotly_chart(fig_scatter, use_container_width=True)

# ============================================================
# Tab 2: What-If Simulator (Tweak 2)
# ============================================================
with tab_whatif:
    st.subheader("🔮 What-If Margin Simulator")
    st.markdown("Adjust COGS and competitor price to see how margins change in real-time. "
                "Use this to evaluate procurement decisions or pricing strategies.")

    if products_df.empty:
        st.warning("No products available. Seed the database first (`make seed`).")
    else:
        # Product selector
        sim_product = st.selectbox(
            "Select product:",
            options=products_df["name"].tolist(),
            key="sim_product",
        )

        prod_row = products_df[products_df["name"] == sim_product].iloc[0]
        current_cogs = float(prod_row["cogs_tnd"])
        current_price = float(prod_row["b2c_price_tnd"]) if pd.notna(prod_row["b2c_price_tnd"]) else 30.0
        threshold = float(prod_row["alert_threshold_pct"]) if pd.notna(prod_row["alert_threshold_pct"]) else 40.0

        # Sliders
        col_sliders, col_results = st.columns([1, 2])

        with col_sliders:
            st.markdown("#### Adjust Parameters")

            cogs_adjust = st.slider(
                "COGS Adjustment (±20%)",
                min_value=-20,
                max_value=20,
                value=0,
                step=1,
                format="%d%%",
                help="Adjust the Cost of Goods Sold by up to ±20%.",
            )

            price_adjust = st.slider(
                "Competitor Price Adjustment (±30%)",
                min_value=-30,
                max_value=30,
                value=0,
                step=1,
                format="%d%%",
                help="Adjust the competitor price by up to ±30%.",
            )

            # Calculate adjusted values
            adjusted_cogs = round(current_cogs * (1 + cogs_adjust / 100), 3)
            adjusted_price = round(current_price * (1 + price_adjust / 100), 3)

            st.markdown(f"**Current COGS:** {current_cogs:.3f} TND")
            st.markdown(f"**Adjusted COGS:** {adjusted_cogs:.3f} TND")
            st.markdown(f"**Current Price:** {current_price:.3f} TND")
            st.markdown(f"**Adjusted Price:** {adjusted_price:.3f} TND")
            st.markdown(f"**Alert Threshold:** {threshold:.0f}%")

        with col_results:
            st.markdown("#### Simulated Margins")

            # Calculate new margins
            b2c_price_new, b2b_price_new, b2c_margin_new, b2b_margin_new = calculate_margins(
                adjusted_cogs, adjusted_price, B2B_DISCOUNT_FACTOR
            )

            b2c_alert_new, b2b_alert_new = check_margin_threshold(b2c_margin_new, b2b_margin_new, threshold)

            # Original margins for comparison
            b2c_price_orig, b2b_price_orig, b2c_margin_orig, b2b_margin_orig = calculate_margins(
                current_cogs, current_price, B2B_DISCOUNT_FACTOR
            )

            # B2C gauge
            col_b2c, col_b2b = st.columns(2)

            with col_b2c:
                fig_sim_b2c = go.Figure()
                fig_sim_b2c.add_trace(go.Indicator(
                    mode="gauge+number+delta",
                    value=b2c_margin_new,
                    delta={"reference": b2c_margin_orig, "suffix": "%"},
                    title={"text": "B2C Margin"},
                    gauge={
                        "axis": {"range": [-50, 80]},
                        "bar": {"color": "#dc2626" if b2c_alert_new else "#16a34a"},
                        "steps": [
                            {"range": [-50, threshold - 10], "color": "rgba(220,38,38,0.3)"},
                            {"range": [threshold - 10, threshold], "color": "rgba(245,158,11,0.3)"},
                            {"range": [threshold, 80], "color": "rgba(22,163,74,0.3)"},
                        ],
                        "threshold": {
                            "line": {"color": "white", "width": 3},
                            "thickness": 0.75,
                            "value": threshold,
                        },
                    },
                ))
                fig_sim_b2c.update_layout(template="plotly_dark", height=300)
                st.plotly_chart(fig_sim_b2c, use_container_width=True)

                if b2c_alert_new:
                    st.error(f"🚨 B2C margin ({b2c_margin_new:.1f}%) is below threshold ({threshold:.0f}%)!")
                else:
                    st.success(f"✅ B2C margin ({b2c_margin_new:.1f}%) is above threshold ({threshold:.0f}%)")

            with col_b2b:
                fig_sim_b2b = go.Figure()
                fig_sim_b2b.add_trace(go.Indicator(
                    mode="gauge+number+delta",
                    value=b2b_margin_new,
                    delta={"reference": b2b_margin_orig, "suffix": "%"},
                    title={"text": "B2B Margin"},
                    gauge={
                        "axis": {"range": [-50, 80]},
                        "bar": {"color": "#dc2626" if b2b_alert_new else "#16a34a"},
                        "steps": [
                            {"range": [-50, threshold - 10], "color": "rgba(220,38,38,0.3)"},
                            {"range": [threshold - 10, threshold], "color": "rgba(245,158,11,0.3)"},
                            {"range": [threshold, 80], "color": "rgba(22,163,74,0.3)"},
                        ],
                        "threshold": {
                            "line": {"color": "white", "width": 3},
                            "thickness": 0.75,
                            "value": threshold,
                        },
                    },
                ))
                fig_sim_b2b.update_layout(template="plotly_dark", height=300)
                st.plotly_chart(fig_sim_b2b, use_container_width=True)

                if b2b_alert_new:
                    st.error(f"🚨 B2B margin ({b2b_margin_new:.1f}%) is below threshold ({threshold:.0f}%)!")
                else:
                    st.success(f"✅ B2B margin ({b2b_margin_new:.1f}%) is above threshold ({threshold:.0f}%)")

            # Summary table — convert all values to strings to avoid
            # pyarrow ArrowInvalid errors from mixed float/str columns
            st.markdown("#### Scenario Summary")

            def fmt_delta(delta, is_pct=False):
                if delta == "":
                    return "—"
                suffix = "%" if is_pct else ""
                sign = "+" if delta >= 0 else ""
                return f"{sign}{delta:.2f}{suffix}"

            summary = pd.DataFrame([
                {"Metric": "COGS (TND)", "Original": f"{current_cogs:.3f}", "Adjusted": f"{adjusted_cogs:.3f}", "Delta": fmt_delta(adjusted_cogs - current_cogs)},
                {"Metric": "B2C Price (TND)", "Original": f"{b2c_price_orig:.3f}", "Adjusted": f"{b2c_price_new:.3f}", "Delta": fmt_delta(b2c_price_new - b2c_price_orig)},
                {"Metric": "B2B Price (TND)", "Original": f"{b2b_price_orig:.3f}", "Adjusted": f"{b2b_price_new:.3f}", "Delta": fmt_delta(b2b_price_new - b2b_price_orig)},
                {"Metric": "B2C Margin (%)", "Original": f"{b2c_margin_orig:.2f}", "Adjusted": f"{b2c_margin_new:.2f}", "Delta": fmt_delta(b2c_margin_new - b2c_margin_orig, is_pct=True)},
                {"Metric": "B2B Margin (%)", "Original": f"{b2b_margin_orig:.2f}", "Adjusted": f"{b2b_margin_new:.2f}", "Delta": fmt_delta(b2b_margin_new - b2b_margin_orig, is_pct=True)},
                {"Metric": "B2C Alert", "Original": "🚨 Yes" if b2c_margin_orig < threshold else "✅ No", "Adjusted": "🚨 Yes" if b2c_alert_new else "✅ No", "Delta": "—"},
                {"Metric": "B2B Alert", "Original": "🚨 Yes" if b2b_margin_orig < threshold else "✅ No", "Adjusted": "🚨 Yes" if b2b_alert_new else "✅ No", "Delta": "—"},
            ])
            st.table(summary)

st.markdown("---")
st.caption("🛡️ Kinz Margin Guardian — Automated margin monitoring for KINZ natural cosmetics. Data from PostgreSQL, margins calculated by Airflow DAG.")
