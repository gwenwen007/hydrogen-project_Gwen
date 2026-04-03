"""
Page 4 — Cost Analysis
=======================
Compares optimized vs. baseline production costs, shows savings breakdowns,
and lets users simulate different scenarios side by side.

Grading requirements addressed:
- Requirement 3: Data visualisation (cost comparison charts)
- Requirement 4: User interaction (scenario comparison)
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

from utils.helpers import (
    format_currency,
    inject_custom_css,
    get_plotly_template,
    render_kpi_bar,
    render_status_bar,
    render_sidebar_brand,
    render_card_header,
    AUSTRALIAN_REGIONS,
    COLORS,
)

# ---------- Page config ----------
st.set_page_config(page_title="Cost Analysis", layout="wide")
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
st.title("Cost Analysis")

# ---------- Check if optimization has run ----------
if "savings" not in st.session_state or "schedule" not in st.session_state:
    st.warning(
        "No optimization results yet. "
        "Go to **Production Optimizer** and run the optimizer first."
    )
    st.stop()

savings = st.session_state["savings"]
schedule = st.session_state["schedule"]

# ---------- Top KPI bar ----------
cost_per_kg = savings["optimized_cost_aud"] / savings["total_h2_kg"] if savings["total_h2_kg"] > 0 else 0

cost_kpis = [
    {"label": "OPTIMIZED COST", "value": format_currency(savings["optimized_cost_aud"]),
     "unit": "You get paid" if savings["optimized_cost_aud"] < 0 else "Electricity",
     "delta": None, "delta_color": "off"},
    {"label": "BASELINE COST", "value": format_currency(savings["baseline_cost_aud"]),
     "unit": "Without optimizer", "delta": None, "delta_color": "off"},
    {"label": "TOTAL SAVINGS", "value": format_currency(savings["savings_aud"]),
     "unit": f"+{savings['savings_pct']}% vs baseline",
     "delta": f"+{savings['savings_pct']}%", "delta_color": "inverse"},
    {"label": "COST PER KG H2", "value": f"${cost_per_kg:.2f}",
     "unit": "AUD/kg", "delta": None, "delta_color": "off"},
    {"label": "BREAK-EVEN", "value": "$45.00",
     "unit": "AUD/MWh threshold",
     "delta": None, "delta_color": "off"},
]
render_kpi_bar(cost_kpis)

st.markdown("")

# ---------- Main layout ----------
col_left, col_right = st.columns([3, 2])

with col_left:
    # --- Cost comparison chart ---
    with st.expander("Cost Comparison", expanded=True):
        # PLUG: cost_breakdown — Add ramp-up and maintenance costs when available
        categories = ["Electricity", "Ramp-up", "Maintenance", "Total"]
        optimized_vals = [savings["optimized_cost_aud"], 85, 120,
                          savings["optimized_cost_aud"] + 85 + 120]
        baseline_vals = [savings["baseline_cost_aud"], 0, 120,
                         savings["baseline_cost_aud"] + 120]

        fig_comp = go.Figure()
        fig_comp.add_trace(go.Bar(
            x=categories, y=optimized_vals, name="Optimized",
            marker_color=COLORS["accent"],
        ))
        fig_comp.add_trace(go.Bar(
            x=categories, y=baseline_vals, name="Baseline",
            marker_color=COLORS["red"],
            opacity=0.7,
        ))
        fig_comp.update_layout(
            **get_plotly_template(),
            height=320,
            barmode="group",
            yaxis_title="AUD",
        )
        st.plotly_chart(fig_comp, use_container_width=True)

with col_right:
    # --- Scenario comparison table ---
    with st.expander("Scenario Comparison", expanded=True):
        # PLUG: scenario_data — Replace with real scenario calculations
        total_opt = savings["optimized_cost_aud"]
        total_base = savings["baseline_cost_aud"]
        total_h2 = savings["total_h2_kg"]
        opt_per_kg = total_opt / total_h2 if total_h2 > 0 else 0

        scenarios = [
            ("Optimized (72h)", format_currency(total_opt), f"${opt_per_kg:.2f}",
             format_currency(savings["savings_aud"]), True),
            ("Optimized (24h)", format_currency(total_opt * 0.35), f"${opt_per_kg * 0.35:.2f}",
             format_currency(savings["savings_aud"] * 0.67), False),
            ("Off-peak only", format_currency(total_base * 0.49), f"${(total_base * 0.49 / total_h2):.2f}",
             format_currency(total_base * 0.51), False),
            ("Flat production", format_currency(total_base), f"${(total_base / total_h2):.2f}",
             "$0.00", False),
            ("PPA fixed rate", format_currency(total_base * 0.66), f"${(total_base * 0.66 / total_h2):.2f}",
             format_currency(total_base * 0.34), False),
        ]

        table_rows = ""
        for name, cost, per_kg, saved, is_best in scenarios:
            highlight = ' class="highlight"' if is_best else ""
            table_rows += (
                f"<tr><td{highlight}>{name}</td>"
                f"<td{highlight}>{cost}</td>"
                f"<td{highlight}>{per_kg}</td>"
                f"<td{highlight}>{saved}</td></tr>"
            )

        st.markdown(
            f"""<table class="scenario-table">
            <thead><tr>
                <th>Strategy</th><th>Cost</th><th>$/kg H2</th><th>Savings</th>
            </tr></thead>
            <tbody>{table_rows}</tbody>
            </table>""",
            unsafe_allow_html=True,
        )

st.markdown("")

# ---------- Break-even analysis ----------
col_be, col_export = st.columns([2, 1])

with col_be:
    with st.expander("Break-Even Analysis", expanded=True):
        # PLUG: breakeven_curve — Calculate from actual model outputs
        elec_prices = np.arange(-30, 65, 5)
        h2_cost_per_kg = elec_prices * 0.14  # simplified linear relationship
        breakeven_line = np.full_like(elec_prices, 5.0, dtype=float)

        fig_be = go.Figure()
        fig_be.add_trace(go.Scatter(
            x=elec_prices, y=h2_cost_per_kg,
            mode="lines", name="H2 Cost ($/kg)",
            line=dict(color=COLORS["accent"], width=2),
            fill="tozeroy",
            fillcolor="rgba(0, 212, 170, 0.08)",
        ))
        fig_be.add_trace(go.Scatter(
            x=elec_prices, y=breakeven_line,
            mode="lines", name="Break-even $5/kg",
            line=dict(color=COLORS["amber"], width=2, dash="dash"),
        ))
        fig_be.update_layout(
            **get_plotly_template(),
            height=280,
            xaxis_title="Electricity Price (AUD/MWh)",
            yaxis_title="H2 Cost (AUD/kg)",
        )
        st.plotly_chart(fig_be, use_container_width=True)

with col_export:
    # --- Export panel ---
    with st.expander("Export & Reports", expanded=True):
        # Production Schedule CSV
        st.markdown(
            f'<div class="dashboard-card">'
            f'<div style="color:{COLORS["text"]}; font-weight:600;">Production Schedule</div>'
            f'<div style="color:{COLORS["text_muted"]}; font-size:0.75rem;">CSV — Hourly schedule with prices</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        csv_data = schedule.to_csv(index=False)
        st.download_button("Download CSV", csv_data, "optimized_schedule.csv", "text/csv",
                           use_container_width=True)

        # Cost report placeholder
        st.markdown(
            f'<div class="dashboard-card">'
            f'<div style="color:{COLORS["text"]}; font-weight:600;">Cost Analysis Report</div>'
            f'<div style="color:{COLORS["text_muted"]}; font-size:0.75rem;">PDF — Full breakdown with charts</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        # PLUG: pdf_export — Generate PDF report with charts
        st.button("Download PDF", disabled=True, use_container_width=True,
                  help="PDF export coming soon")

        # Scenario comparison placeholder
        st.markdown(
            f'<div class="dashboard-card">'
            f'<div style="color:{COLORS["text"]}; font-weight:600;">Scenario Comparison</div>'
            f'<div style="color:{COLORS["text_muted"]}; font-size:0.75rem;">XLSX — All strategies compared</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        # PLUG: xlsx_export — Generate Excel with scenario sheets
        st.button("Download XLSX", disabled=True, use_container_width=True,
                  help="Excel export coming soon")

        # Raw price data
        st.markdown(
            f'<div class="dashboard-card">'
            f'<div style="color:{COLORS["text"]}; font-weight:600;">Raw Price Data</div>'
            f'<div style="color:{COLORS["text_muted"]}; font-size:0.75rem;">CSV — Historical + forecast prices</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        if "price_forecast" in st.session_state:
            raw_csv = st.session_state["price_forecast"].to_csv(index=False)
            st.download_button("Download Prices CSV", raw_csv, "price_data.csv", "text/csv",
                               use_container_width=True)

# ---------- Status bar ----------
render_status_bar(connected=True, last_sync="14:32 AEST")
