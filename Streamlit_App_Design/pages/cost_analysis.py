"""
cost_analysis.py — Cost Analysis page.

Will show:
  - Cost breakdown donut chart
  - Historical cost trend line chart
  - Sensitivity analysis table/chart
  - CSV download button for data export
"""

import streamlit as st
from Streamlit_App_Design.style import COLORS


def render():
    """Draw the Cost Analysis page.  Called by app.py."""

    st.markdown(
        f"""
        <div style="background-color:{COLORS['bg_card']};
                    border:1px solid {COLORS['border']};
                    border-radius:8px; padding:2rem; margin:1rem 0;
                    text-align:center;">
            <h2 style="color:{COLORS['text_primary']}; margin:0;">
                Cost Analysis
            </h2>
            <p style="color:{COLORS['text_secondary']}; margin-top:0.5rem;">
                Cost breakdown, trend chart, sensitivity analysis, and CSV export will go here.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
