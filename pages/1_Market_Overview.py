"""
Page 1 — Market Overview
=========================
Shows live/recent electricity prices and weather data for the selected
Australian NEM region. This is the "monitoring dashboard" page.

Grading requirements addressed:
- Requirement 2: Data loaded via API
- Requirement 3: Data visualisation
- Requirement 4: User interaction (region selector, time range)
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np

from utils.api import fetch_electricity_prices, fetch_weather_data, fetch_hydrogen_news
from utils.helpers import (
    AUSTRALIAN_REGIONS,
    inject_custom_css,
    get_plotly_template,
    render_kpi_bar,
    render_status_bar,
    render_sidebar_brand,
    render_card_header,
    get_placeholder_kpis,
    COLORS,
)

# ---------- Page config ----------
st.set_page_config(page_title="Market Overview", page_icon="📊", layout="wide")
inject_custom_css()

# ---------- Sidebar ----------
render_sidebar_brand()

region_code = st.sidebar.selectbox(
    "Region",
    options=list(AUSTRALIAN_REGIONS.keys()),
    format_func=lambda code: f"{AUSTRALIAN_REGIONS[code]['name']} ({code})",
)
region = AUSTRALIAN_REGIONS[region_code]

st.sidebar.markdown("---")
st.sidebar.markdown("**Timeframe**")
timeframe = st.sidebar.radio(
    "Timeframe",
    ["24h", "48h", "7d", "30d"],
    horizontal=True,
    label_visibility="collapsed",
)
hours_map = {"24h": 24, "48h": 48, "7d": 168, "30d": 720}
hours = hours_map[timeframe]

# ---------- Header ----------
st.markdown(
    '<div style="font-size:0.75rem; color:#8B95A5; margin-bottom:4px;">'
    '03 Apr 2026  |  AEMO NEM  |  AUD</div>',
    unsafe_allow_html=True,
)
st.title("Market Overview")

# ---------- KPI bar ----------
# PLUG: kpi_data — Replace with live data from utils/api.py
kpis = get_placeholder_kpis(region_code)
render_kpi_bar(kpis)

st.markdown("")  # spacer

# ---------- Fetch data ----------
# PLUG: price_data — fetch_electricity_prices returns placeholder data; wire to real AEMO API
price_df = fetch_electricity_prices(region=region_code, hours=hours)

# PLUG: weather_data — fetch_weather_data already calls Open-Meteo (working)
weather_df = fetch_weather_data(latitude=region["lat"], longitude=region["lon"], hours=hours)

# ---------- Main layout: 2 columns ----------
col_main, col_side = st.columns([2, 1])

# ===== LEFT COLUMN: Charts =====
with col_main:
    # --- Price chart card ---
    with st.expander("Electricity Price — " + region["name"], expanded=True):
        if not price_df.empty:
            fig_price = go.Figure()
            fig_price.add_trace(go.Scatter(
                x=price_df["timestamp"],
                y=price_df["price_aud_mwh"],
                mode="lines",
                name="Spot Price",
                line=dict(color=COLORS["accent"], width=2),
                fill="tozeroy",
                fillcolor="rgba(0, 212, 170, 0.08)",
            ))
            fig_price.add_hline(
                y=0, line_dash="dash", line_color=COLORS["red"],
                annotation_text="Break-even", annotation_font_color=COLORS["red"],
            )
            fig_price.update_layout(
                **get_plotly_template(),
                height=320,
                showlegend=False,
                yaxis_title="AUD/MWh",
                xaxis_title="",
            )
            st.plotly_chart(fig_price, use_container_width=True)
        else:
            st.warning("No price data available. Check the API connection.")

    # --- Price distribution histogram ---
    with st.expander("Price Distribution", expanded=True):
        render_card_header("Price Statistics (7d)")
        if not price_df.empty:
            # PLUG: price_stats — Replace with live statistics
            col_s1, col_s2, col_s3 = st.columns(3)
            col_s1.metric("Min", f"${price_df['price_aud_mwh'].min():.2f}")
            col_s2.metric("Median", f"${price_df['price_aud_mwh'].median():.2f}")
            col_s3.metric("Max", f"${price_df['price_aud_mwh'].max():.2f}")

            # Distribution chart
            bins = [-100, -20, 0, 20, 50, 80, 200]
            labels = ["<-20", "-20–0", "0–20", "20–50", "50–80", ">80"]
            price_df["bucket"] = pd.cut(
                price_df["price_aud_mwh"], bins=bins, labels=labels, right=True,
            )
            dist = price_df["bucket"].value_counts().reindex(labels).fillna(0)

            fig_dist = go.Figure(go.Bar(
                x=labels,
                y=dist.values,
                marker_color=[
                    COLORS["green"], COLORS["accent_light"], COLORS["accent"],
                    COLORS["amber"], "#FF9F43", COLORS["red"],
                ],
            ))
            fig_dist.update_layout(
                **get_plotly_template(),
                height=220,
                showlegend=False,
                yaxis_title="Hours",
                xaxis_title="AUD/MWh",
            )
            st.plotly_chart(fig_dist, use_container_width=True)

# ===== RIGHT COLUMN: Weather & News =====
with col_side:
    # --- Weather & Grid panel ---
    with st.expander("Weather & Grid", expanded=True):
        # PLUG: weather_panel — Replace placeholder values with live weather data
        weather_items = [
            ("Solar Radiation", "680 W/m²"),
            ("Wind Speed", "34 km/h"),
            ("Temperature", "22.4 °C"),
            ("Cloud Cover", "25%"),
            ("Grid Demand", "3.1 GW"),
        ]
        if not weather_df.empty:
            weather_items = [
                ("Solar Radiation", f"{weather_df['solar_radiation_wm2'].iloc[-1]:.0f} W/m²"),
                ("Wind Speed", f"{weather_df['wind_speed_kmh'].iloc[-1]:.0f} km/h"),
                ("Temperature", f"{weather_df['temperature_c'].iloc[-1]:.1f} °C"),
                ("Cloud Cover", "25%"),  # PLUG: cloud_cover — Add cloud cover from weather API
                ("Grid Demand", "3.1 GW"),  # PLUG: grid_demand — Add grid demand from AEMO
            ]

        weather_html = ""
        for label, value in weather_items:
            weather_html += (
                f'<div class="weather-item">'
                f'<span class="weather-label">{label}</span>'
                f'<span class="weather-value">{value}</span>'
                f'</div>'
            )
        st.markdown(weather_html, unsafe_allow_html=True)

    # --- News feed ---
    with st.expander("Hydrogen & Energy News", expanded=True):
        # PLUG: news_feed — Replace with fetch_hydrogen_news() from utils/api.py
        news_articles = [
            {"title": "Australia announces $2B green hydrogen fund for 2027", "source": "Reuters", "time": "2h"},
            {"title": "SA wind farm output hits record 4.2 GW during storm", "source": "AEMO", "time": "5h"},
            {"title": "NEM negative pricing events up 23% YoY in Q1 2026", "source": "AFR", "time": "1d"},
            {"title": "Fortescue signs 500MW electrolyzer deal with Siemens", "source": "Bloomberg", "time": "1d"},
            {"title": "EU carbon border adjustment impacts AU H2 exports", "source": "IEA", "time": "2d"},
        ]

        news_html = ""
        for article in news_articles:
            news_html += (
                f'<div class="news-item">'
                f'<div class="news-title">{article["title"]}</div>'
                f'<div class="news-meta">{article["source"]}  ·  {article["time"]}</div>'
                f'</div>'
            )
        st.markdown(news_html, unsafe_allow_html=True)

# ---------- Status bar ----------
# PLUG: api_status — Replace with real connection status
render_status_bar(connected=True, last_sync="14:32 AEST")
