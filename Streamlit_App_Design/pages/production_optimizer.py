"""
production_optimizer.py — Production Optimizer page.

Will show:
  - Input controls (electrolyser capacity slider, break-even price)
  - Optimal production schedule (green = produce, red = hold)
  - Cost summary KPIs
  - Optimised vs. naive comparison
"""

import streamlit as st
from Streamlit_App_Design.style import COLORS


def render():
    """Draw the Production Optimizer page.  Called by app.py."""

    st.markdown(
        f"""
        <div style="background-color:{COLORS['bg_card']};
                    border:1px solid {COLORS['border']};
                    border-radius:8px; padding:2rem; margin:1rem 0;
                    text-align:center;">
            <h2 style="color:{COLORS['text_primary']}; margin:0;">
                Production Optimizer
            </h2>
            <p style="color:{COLORS['text_secondary']}; margin-top:0.5rem;">
                Electrolyser controls, schedule chart, and cost comparison will go here.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
