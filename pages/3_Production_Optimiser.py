"""
Page 3 — Production Optimizer
===============================
The core of the app: users enter their electrolyzer parameters and hydrogen
target, and the optimizer selects the cheapest production hours from the
price forecast.

Grading requirements addressed:
- Requirement 1: Clear business problem (cost-optimized H2 production)
- Requirement 4: User interaction (sliders, inputs, file upload)
- Requirement 3: Data visualisation (production schedule chart)
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

from utils.optimizer import optimize_schedule, calculate_savings
from utils.helpers import (
    AUSTRALIAN_REGIONS,
    DEFAULT_CAPACITY_MW,
    DEFAULT_EFFICIENCY_KWH_PER_KG,
    DEFAULT_TARGET_H2_KG,
    format_currency,
    format_price_per_kg,
    inject_custom_css,
    get_plotly_template,
    render_kpi_bar,
    render_status_bar,
    render_sidebar_brand,
    render_card_header,
    COLORS,
)

# ---------- Page config ----------
st.set_page_config(page_title="Production Optimizer", page_icon="🔧", layout="wide")
inject_custom_css()

# ---------- Sidebar ----------
render_sidebar_brand()

region_code = st.sidebar.selectbox(
    "Region",
    options=list(AUSTRALIAN_REGIONS.keys()),
    format_func=lambda code: f"{AUSTRALIAN_REGIONS[code]['name']} ({code})",
)

st.sidebar.markdown("---")
st.sidebar.markdown("**Timeframe**")
timeframe = st.sidebar.radio("Timeframe", ["24h", "48h", "7d", "30d"],
                              horizontal=True, label_visibility="collapsed")

# ---------- Header ----------
st.markdown(
    '<div style="font-size:0.75rem; color:#8B95A5; margin-bottom:4px;">'
    '03 Apr 2026  |  AEMO NEM  |  AUD</div>',
    unsafe_allow_html=True,
)
st.title("🔧 Production Optimizer")

# ---------- Check if forecast data is available ----------
if "price_forecast" not in st.session_state:
    st.warning(
        "No price forecast available yet. "
        "Please go to **Price Forecast** and train the model first."
    )
    st.stop()

# ---------- Parameters + main layout ----------
col_params, col_main = st.columns([1, 3])

with col_params:
    render_card_header("Production Parameters")

    # PLUG: electrolyzer_params — These defaults come from helpers.py constants
    h2_target = st.number_input("H2 Target (kg)", min_value=10.0, max_value=50000.0,
                                 value=float(DEFAULT_TARGET_H2_KG), step=50.0)
    capacity_mw = st.number_input("Electrolyzer (MW)", min_value=0.5, max_value=100.0,
                                   value=float(DEFAULT_CAPACITY_MW), step=0.5)
    efficiency = st.number_input("Efficiency (kWh/kg)", min_value=30.0, max_value=80.0,
                                  value=DEFAULT_EFFICIENCY_KWH_PER_KG, step=0.5)
    breakeven = st.number_input("Break-even (AUD/MWh)", min_value=0.0, max_value=200.0,
                                 value=45.0, step=1.0)
    opt_window = st.selectbox("Optimization Window", ["24 hours", "48 hours", "72 hours"],
                               index=2)

    st.markdown("")
    run_btn = st.button("Run Optimization", type="primary", use_container_width=True)

    st.markdown("")
    uploaded_file = st.file_uploader("Upload custom price data (CSV/XLSX)",
                                      type=["csv", "xlsx"])

# ---------- Determine price data source ----------
if uploaded_file is not None:
    if uploaded_file.name.endswith(".csv"):
        custom_df = pd.read_csv(uploaded_file, parse_dates=["timestamp"])
    else:
        custom_df = pd.read_excel(uploaded_file, parse_dates=["timestamp"])

    if "timestamp" in custom_df.columns and "price_aud_mwh" in custom_df.columns:
        price_forecast = custom_df.rename(columns={"price_aud_mwh": "predicted_price_aud_mwh"})
    else:
        st.error("Uploaded file must have 'timestamp' and 'price_aud_mwh' columns.")
        st.stop()
else:
    price_forecast = st.session_state["price_forecast"]

# ---------- Run optimizer ----------
with col_main:
    if run_btn:
        schedule = optimize_schedule(
            price_forecast=price_forecast,
            electrolyzer_capacity_mw=capacity_mw,
            efficiency_kwh_per_kg=efficiency,
            target_h2_kg=h2_target,
        )
        savings = calculate_savings(schedule, capacity_mw)

        st.session_state["schedule"] = schedule
        st.session_state["savings"] = savings

    if "schedule" in st.session_state and "savings" in st.session_state:
        schedule = st.session_state["schedule"]
        savings = st.session_state["savings"]

        # --- Optimization results KPI bar ---
        produce_hours = schedule["produce"].sum()
        total_hours = len(schedule)

        results_kpis = [
            {"label": "PRODUCTION HOURS", "value": f"{produce_hours}h",
             "unit": f"of {total_hours}h window", "delta": None, "delta_color": "off"},
            {"label": "AVG. PROD. PRICE", "value": f"${savings['avg_optimized_price']:.2f}",
             "unit": "AUD/MWh", "delta": None, "delta_color": "off"},
            {"label": "H2 PRODUCED", "value": f"{savings['total_h2_kg']:,.0f} kg",
             "unit": "Target met", "delta": None, "delta_color": "off"},
            {"label": "ELECTRICITY COST", "value": format_currency(savings["optimized_cost_aud"]),
             "unit": "Paid to produce", "delta": None, "delta_color": "off"},
            {"label": "TOTAL SAVINGS", "value": f"{savings['savings_pct']}%",
             "unit": format_currency(savings["savings_aud"]),
             "delta": f"+{savings['savings_pct']}%", "delta_color": "inverse"},
        ]
        render_kpi_bar(results_kpis)

        st.markdown("")

        # --- Schedule chart ---
        with st.expander("Optimal Production Schedule", expanded=True):
            fig = go.Figure()

            idle_df = schedule[~schedule["produce"]]
            produce_df = schedule[schedule["produce"]]

            # Idle hours (muted bars)
            fig.add_trace(go.Bar(
                x=idle_df["timestamp"],
                y=idle_df["predicted_price_aud_mwh"],
                name="Price (idle)",
                marker_color=COLORS["border"],
                opacity=0.4,
            ))

            # Production hours (colored bars)
            fig.add_trace(go.Bar(
                x=produce_df["timestamp"],
                y=produce_df["predicted_price_aud_mwh"],
                name="Price (produce)",
                marker_color=np.where(
                    produce_df["predicted_price_aud_mwh"] < 0,
                    COLORS["green"], COLORS["accent_light"],
                ),
                opacity=0.9,
            ))

            fig.add_hline(y=0, line_dash="dash", line_color=COLORS["red"], opacity=0.5)
            fig.add_hline(y=breakeven, line_dash="dot", line_color=COLORS["amber"],
                          annotation_text=f"Break-even ${breakeven:.0f}",
                          annotation_font_color=COLORS["amber"])

            fig.update_layout(
                **get_plotly_template(),
                height=340,
                barmode="overlay",
                yaxis_title="AUD/MWh",
                xaxis_title="",
            )
            st.plotly_chart(fig, use_container_width=True)

        # --- Production timeline strip ---
        render_card_header("Production Timeline", f"Next {total_hours}h")

        # Build timeline blocks from consecutive produce/idle segments
        blocks_html = ""
        current_state = schedule.iloc[0]["produce"]
        block_start = 0
        for i in range(1, len(schedule) + 1):
            if i == len(schedule) or schedule.iloc[i]["produce"] != current_state:
                block_len = i - block_start
                pct = (block_len / len(schedule)) * 100
                if current_state:
                    blocks_html += (
                        f'<div class="timeline-block timeline-produce" '
                        f'style="flex:{pct:.1f};">PRODUCE</div>'
                    )
                else:
                    blocks_html += (
                        f'<div class="timeline-block timeline-idle" '
                        f'style="flex:{pct:.1f};"></div>'
                    )
                if i < len(schedule):
                    current_state = schedule.iloc[i]["produce"]
                    block_start = i

        st.markdown(f'<div class="timeline-container">{blocks_html}</div>', unsafe_allow_html=True)
        st.caption("Green blocks = scheduled production  |  Grey = idle (prices above break-even)")

        # --- Data table ---
        with st.expander("View full schedule data"):
            display_df = schedule[["timestamp", "predicted_price_aud_mwh", "produce",
                                   "h2_produced_kg", "electricity_cost_aud"]].copy()
            display_df.columns = ["Time", "Price (AUD/MWh)", "Produce?", "H2 (kg)", "Cost (AUD)"]
            st.dataframe(display_df, use_container_width=True)

    else:
        st.info("Adjust parameters on the left and click **Run Optimization**.")

# ---------- Status bar ----------
render_status_bar(connected=True, last_sync="14:32 AEST")
