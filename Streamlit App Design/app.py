"""
Hydrogen Production Optimizer — Main Entry Point
=================================================
This is the landing page of the Streamlit app.
Run it with:  streamlit run app.py

The pages/ folder contains the individual pages that appear in the sidebar.
The utils/ folder contains shared logic (API calls, ML model, optimizer).
"""

import streamlit as st
from utils.helpers import (
    inject_custom_css,
    render_kpi_bar,
    render_status_bar,
    render_sidebar_brand,
    get_placeholder_kpis,
)

# ---------- Page config (must be the first Streamlit command) ----------
st.set_page_config(
    page_title="H2 Production Optimizer",
    layout="wide",
)

inject_custom_css()

# ---------- Sidebar ----------
render_sidebar_brand()

# PLUG: region_selector — Wire to session state shared across all pages
region = st.sidebar.selectbox(
    "Region",
    ["SA1", "NSW1", "VIC1", "QLD1", "TAS1"],
    format_func=lambda r: {
        "SA1": "South Australia (SA1)",
        "NSW1": "New South Wales (NSW1)",
        "VIC1": "Victoria (VIC1)",
        "QLD1": "Queensland (QLD1)",
        "TAS1": "Tasmania (TAS1)",
    }.get(r, r),
)

# ---------- Header ----------
st.markdown(
    '<div style="font-size:0.75rem; color:#8B95A5; margin-bottom:4px;">'
    '03 Apr 2026  |  AEMO NEM  |  AUD</div>',
    unsafe_allow_html=True,
)
st.title("Hydrogen Production Optimizer")
st.caption("Utilizing Negative Electricity Prices for Green Hydrogen Production")

# ---------- KPI bar ----------
# PLUG: kpi_data — Replace with live data from utils/api.py
kpis = get_placeholder_kpis(region)
render_kpi_bar(kpis)

st.divider()

# ---------- Navigation overview ----------
st.markdown(
    """
    Use the **sidebar** to navigate between pages:

    1. **Market Overview** — Live electricity prices, weather data, and hydrogen news
    2. **Price Forecast** — ML-based price predictions with confidence bands
    3. **Production Optimizer** — Enter your parameters and get an optimal schedule
    4. **Cost Analysis** — Compare strategies, estimate savings, and export reports
    """
)

# ---------- Status bar ----------
# PLUG: api_status — Replace with real connection status and last sync time
render_status_bar(connected=True, last_sync="14:32 AEST")
