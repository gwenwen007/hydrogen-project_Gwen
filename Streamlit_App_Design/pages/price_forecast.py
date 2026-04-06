"""
price_forecast.py — Price Forecast page.

Will show:
  - Model selector dropdown (Linear Regression / Random Forest / XGBoost)
  - Forecast chart with confidence interval
  - Model performance metrics (RMSE, MAE, R²)
  - Feature importance bar chart
"""

import streamlit as st
from Streamlit_App_Design.style import COLORS


def render():
    """Draw the Price Forecast page.  Called by app.py."""

    st.markdown(
        f"""
        <div style="background-color:{COLORS['bg_card']};
                    border:1px solid {COLORS['border']};
                    border-radius:8px; padding:2rem; margin:1rem 0;
                    text-align:center;">
            <h2 style="color:{COLORS['text_primary']}; margin:0;">
                Price Forecast
            </h2>
            <p style="color:{COLORS['text_secondary']}; margin-top:0.5rem;">
                Model selector, forecast chart, metrics, and feature importance will go here.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
