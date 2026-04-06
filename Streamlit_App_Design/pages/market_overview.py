"""
market_overview.py — Market Overview page (landing page / dashboard).

This is the first page the user sees.  It will eventually show:
  - KPI cards (current price, 24h change, 7-day avg, grid demand)
  - A main price chart with click-to-expand indicator modal
  - A price heatmap, regional comparison, and news/alerts cards

For now it just shows placeholder text so the app shell works.
"""

import streamlit as st
from Streamlit_App_Design.style import COLORS


def render():
    """Draw the Market Overview page.  Called by app.py."""

    # Placeholder — will be replaced with actual dashboard content
    st.markdown(
        f"""
        <div style="background-color:{COLORS['bg_card']};
                    border:1px solid {COLORS['border']};
                    border-radius:8px; padding:2rem; margin:1rem 0;
                    text-align:center;">
            <h2 style="color:{COLORS['text_primary']}; margin:0;">
                Market Overview
            </h2>
            <p style="color:{COLORS['text_secondary']}; margin-top:0.5rem;">
                KPI cards, price chart, heatmap, and news will go here.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
