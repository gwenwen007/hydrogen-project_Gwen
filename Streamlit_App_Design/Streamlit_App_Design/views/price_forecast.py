"""
price_forecast.py — Price Forecast & Carbon Intensity page.

This page combines:
  1. A Linear Regression price forecast trained on real AEMO data
  2. Carbon intensity trends from the Electricity Maps API

The ML model is deliberately simple (as required by the course):
  - Input features: hour_of_day, day_of_week
  - Output: predicted electricity price (AUD/MWh)
  - Method: sklearn LinearRegression (~6 lines of core ML code)

Data sources:
  - Historical prices: data/electricity_prices/ (real AEMO CSVs)
  - Carbon intensity:  data/carbon_intensity/   (real Electricity Maps CSVs)
  - ML model:          data/price_forecast_model.py
"""

import streamlit as st
import plotly.graph_objects as go
from style import COLORS
from components import metric_card, dashboard_card, stats_row

# ── Real data imports (no more sample_data.py!) ──
# run_forecast() trains a LinearRegression on AEMO data and returns
# a dict with timestamps, actual, predicted, bounds, and metrics.
from data.price_forecast_model import run_forecast

# get_carbon_intensity() reads real CSV files from Electricity Maps.
# Moved to its own module so this page no longer depends on sample_data.
from data.carbon_intensity_loader import get_carbon_intensity


def render():
    """Draw the Price Forecast & Carbon Intensity page.  Called by app.py."""

    # ── Get the selected region from the sidebar ──
    # The sidebar stores e.g. "New South Wales (NSW)" in session state.
    # We extract just "NSW" for the data loaders.
    full_region = st.session_state.get("region", "New South Wales (NSW)")
    region_short = full_region.split("(")[-1].replace(")", "").strip()

    # ==============================================================
    # SECTION 1: PRICE FORECAST (Linear Regression)
    # ==============================================================

    # ── Horizon selector ──
    # Lets the user choose how far ahead to forecast.
    # Each switch re-trains the model and updates the chart.
    horizon_label = st.radio(
        label="Forecast Horizon",
        options=["24 h", "48 h", "72 h"],
        index=1,                                       # default: 48 h
        horizontal=True,
        key="forecast_horizon",
    )

    # Convert label to integer hours: "48 h" → 48
    horizon_hours = int(horizon_label.split()[0])

    # ── Run the ML forecast ──
    # This trains a LinearRegression on all historical AEMO data
    # for the selected region and forecasts `horizon_hours` ahead.
    # The model learns: price ≈ f(hour_of_day, day_of_week)
    forecast = run_forecast(
        region_abbr=region_short,
        horizon_hours=horizon_hours,
    )

    # Extract metrics for the KPI cards
    metrics = forecast["metrics"]

    # ── KPI row: model performance metrics ──
    # RMSE, MAE, R² — all computed on the last 100 hours of history
    kpi1, kpi2, kpi3 = st.columns(3)

    with kpi1:
        # RMSE — root mean squared error (lower is better)
        rmse_color = COLORS["green"] if metrics["rmse"] < 30 else COLORS["orange"]
        metric_card(
            label="RMSE",
            value=f"{metrics['rmse']:.2f}",
            subtitle="AUD/MWh — lower is better",
            color=rmse_color,
        )

    with kpi2:
        # MAE — mean absolute error (lower is better)
        mae_color = COLORS["green"] if metrics["mae"] < 20 else COLORS["orange"]
        metric_card(
            label="MAE",
            value=f"{metrics['mae']:.2f}",
            subtitle="AUD/MWh — lower is better",
            color=mae_color,
        )

    with kpi3:
        # R² — goodness of fit (closer to 1.0 is better)
        # Note: with a simple 2-feature model, R² will be low —
        # that's expected and honest.  Electricity prices are noisy.
        r2_color = COLORS["green"] if metrics["r2"] > 0.3 else COLORS["orange"]
        metric_card(
            label="R² SCORE",
            value=f"{metrics['r2']:.3f}",
            subtitle="1.0 = perfect fit",
            color=r2_color,
        )

    # Small spacing
    st.markdown("<div style='margin-top:0.8rem;'></div>", unsafe_allow_html=True)

    # ── Forecast chart ──
    def draw_forecast_chart():
        """
        Draw the forecast chart: historical prices + predicted line
        + confidence interval + 'Now' divider.

        Uses real AEMO data for the historical portion and
        LinearRegression predictions for the forecast portion.
        """
        ts         = forecast["timestamps"]
        actual     = forecast["actual"]
        predicted  = forecast["predicted"]
        lower      = forecast["lower_bound"]
        upper      = forecast["upper_bound"]
        hist_hours = forecast["hist_hours"]

        fig = go.Figure()

        # ── Layer 1: Confidence interval (shaded band) ──
        # Upper bound (invisible line)
        fig.add_trace(go.Scatter(
            x=ts, y=upper,
            mode="lines", line=dict(width=0),
            showlegend=False, hoverinfo="skip", name="Upper CI",
        ))
        # Lower bound + fill between upper and lower
        fig.add_trace(go.Scatter(
            x=ts, y=lower,
            mode="lines", line=dict(width=0),
            fill="tonexty",
            fillcolor="rgba(0,102,255,0.10)",
            showlegend=False, hoverinfo="skip", name="Lower CI",
        ))

        # ── Layer 2: Actual prices (historical only) ──
        # Filter out None values (forecast period has no actuals)
        actual_ts = ts[:hist_hours]
        actual_vals = actual[:hist_hours]
        fig.add_trace(go.Scatter(
            x=actual_ts, y=actual_vals,
            mode="lines", name="Actual",
            line=dict(color=COLORS["text_primary"], width=1.5),
        ))

        # ── Layer 3: Predicted prices (full range) ──
        fig.add_trace(go.Scatter(
            x=ts, y=predicted,
            mode="lines", name="Predicted (Linear Regression)",
            line=dict(color=COLORS["accent"], width=2, dash="dash"),
        ))

        # ── "Now" divider line ──
        now_ts = ts[hist_hours]
        # Compute y range from non-None actual values + predicted
        valid_actual = [v for v in actual if v is not None]
        all_vals = valid_actual + predicted
        y_min = min(all_vals) - 10
        y_max = max(all_vals) + 10

        fig.add_trace(go.Scatter(
            x=[now_ts, now_ts], y=[y_min, y_max],
            mode="lines",
            line=dict(color=COLORS["yellow"], width=1, dash="dash"),
            showlegend=False, hoverinfo="skip", name="Now",
        ))
        fig.add_annotation(
            x=now_ts, y=y_max, text="Now",
            showarrow=False,
            font=dict(color=COLORS["yellow"], size=10),
            yshift=10,
        )

        # ── Chart styling ──
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color=COLORS["text_muted"], size=11),
            margin=dict(l=50, r=20, t=30, b=40),
            height=360,
            xaxis=dict(
                showgrid=False,
                linecolor=COLORS["border"],
                tickfont=dict(color=COLORS["text_muted"], size=10),
            ),
            yaxis=dict(
                title="AUD/MWh",
                title_font=dict(color=COLORS["text_muted"], size=10),
                gridcolor=COLORS["border_light"],
                gridwidth=0.5,
                zeroline=True,
                zerolinecolor=COLORS["border"],
                zerolinewidth=0.5,
                tickfont=dict(color=COLORS["text_muted"], size=10),
            ),
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02,
                xanchor="left", x=0, font=dict(size=10),
            ),
            hovermode="x unified",
        )

        st.plotly_chart(fig, use_container_width=True, key="forecast_chart")

    # ── Forecast modal (expanded view) ──
    def draw_forecast_modal():
        """
        Expanded forecast view with the chart + error histogram + stats.
        """
        import numpy as np

        # Re-draw the chart at larger size
        ts         = forecast["timestamps"]
        actual     = forecast["actual"]
        predicted  = forecast["predicted"]
        lower      = forecast["lower_bound"]
        upper      = forecast["upper_bound"]
        hist_hours = forecast["hist_hours"]

        fig_modal = go.Figure()

        # Confidence band
        fig_modal.add_trace(go.Scatter(
            x=ts, y=upper, mode="lines", line=dict(width=0),
            showlegend=False, hoverinfo="skip",
        ))
        fig_modal.add_trace(go.Scatter(
            x=ts, y=lower, mode="lines", line=dict(width=0),
            fill="tonexty", fillcolor="rgba(0,102,255,0.10)",
            showlegend=False, hoverinfo="skip",
        ))

        # Actual + predicted
        fig_modal.add_trace(go.Scatter(
            x=ts[:hist_hours], y=actual[:hist_hours],
            mode="lines", name="Actual",
            line=dict(color=COLORS["text_primary"], width=1.5),
        ))
        fig_modal.add_trace(go.Scatter(
            x=ts, y=predicted, mode="lines",
            name="Predicted (Linear Regression)",
            line=dict(color=COLORS["accent"], width=2, dash="dash"),
        ))

        # "Now" divider
        now_ts = ts[hist_hours]
        valid_actual = [v for v in actual if v is not None]
        all_vals = valid_actual + predicted
        y_min = min(all_vals) - 10
        y_max = max(all_vals) + 10
        fig_modal.add_trace(go.Scatter(
            x=[now_ts, now_ts], y=[y_min, y_max], mode="lines",
            line=dict(color=COLORS["yellow"], width=1, dash="dash"),
            showlegend=False, hoverinfo="skip",
        ))
        fig_modal.add_annotation(
            x=now_ts, y=y_max, text="Now", showarrow=False,
            font=dict(color=COLORS["yellow"], size=10), yshift=10,
        )

        fig_modal.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color=COLORS["text_muted"], size=11),
            margin=dict(l=50, r=20, t=30, b=40),
            height=400,
            xaxis=dict(showgrid=False, linecolor=COLORS["border"],
                       tickfont=dict(color=COLORS["text_muted"], size=10)),
            yaxis=dict(title="AUD/MWh",
                       title_font=dict(color=COLORS["text_muted"], size=10),
                       gridcolor=COLORS["border_light"], gridwidth=0.5,
                       tickfont=dict(color=COLORS["text_muted"], size=10)),
            legend=dict(orientation="h", yanchor="bottom", y=1.02,
                        xanchor="left", x=0, font=dict(size=10)),
            hovermode="x unified",
        )
        st.plotly_chart(fig_modal, use_container_width=True, key="modal_forecast_chart")

        # ── Error distribution histogram ──
        actual_hist = [v for v in actual[:hist_hours] if v is not None]
        pred_hist = predicted[:len(actual_hist)]
        residuals = np.array(actual_hist) - np.array(pred_hist)

        fig_hist = go.Figure()
        fig_hist.add_trace(go.Histogram(
            x=residuals, nbinsx=30,
            marker_color=COLORS["accent"], opacity=0.7,
        ))
        fig_hist.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color=COLORS["text_muted"], size=10),
            margin=dict(l=40, r=20, t=25, b=30),
            height=200, showlegend=False,
            xaxis=dict(title="Prediction Error (AUD/MWh)",
                       title_font=dict(size=10, color=COLORS["text_muted"]),
                       gridcolor=COLORS["border_light"], gridwidth=0.5,
                       tickfont=dict(color=COLORS["text_muted"], size=9)),
            yaxis=dict(title="Count",
                       title_font=dict(size=10, color=COLORS["text_muted"]),
                       gridcolor=COLORS["border_light"], gridwidth=0.5,
                       tickfont=dict(color=COLORS["text_muted"], size=9)),
        )
        st.markdown(
            f'<div style="font-size:0.8rem;font-weight:600;'
            f'color:{COLORS["text_primary"]};margin:0.8rem 0 0.3rem 0;">'
            f'Error Distribution (Historical Period)</div>',
            unsafe_allow_html=True,
        )
        st.plotly_chart(fig_hist, use_container_width=True, key="modal_error_hist")

        # Stats row
        stats_row([
            {"label": "RMSE", "value": f"{metrics['rmse']:.2f}",
             "subtitle": "AUD/MWh",
             "color": COLORS["green"] if metrics["rmse"] < 30 else COLORS["orange"]},
            {"label": "MAE", "value": f"{metrics['mae']:.2f}",
             "subtitle": "AUD/MWh",
             "color": COLORS["green"] if metrics["mae"] < 20 else COLORS["orange"]},
            {"label": "R²", "value": f"{metrics['r2']:.3f}",
             "subtitle": "1.0 = perfect",
             "color": COLORS["green"] if metrics["r2"] > 0.3 else COLORS["orange"]},
            {"label": "HORIZON", "value": f"{horizon_hours}h",
             "subtitle": f"{horizon_hours // 24}d look-ahead",
             "color": COLORS["accent"]},
        ])

    # Wrap the chart in a dashboard card with modal
    dashboard_card(
        title=f"Price Forecast — Linear Regression — {region_short} ({horizon_hours}h)",
        content_func=draw_forecast_chart,
        modal_title=f"Price Forecast — {region_short} (Detailed View)",
        modal_content_func=draw_forecast_modal,
    )

    # ==============================================================
    # SECTION 2: CARBON INTENSITY
    # ==============================================================
    # This section uses real data from the Electricity Maps API.
    # It shows how clean/dirty the electricity grid is over time.

    # ── Time range selector ──
    carbon_range = st.radio(
        label="Carbon Intensity Period",
        options=["7 days", "30 days", "90 days"],
        index=1,
        horizontal=True,
        key="carbon_range_selector",
    )
    carbon_days = {"7 days": 7, "30 days": 30, "90 days": 90}[carbon_range]

    # Fetch real carbon intensity data
    carbon_df = get_carbon_intensity(region_abbr=region_short, days=carbon_days)

    def draw_carbon_trend():
        """
        Line chart of carbon intensity over time.
        Lower = cleaner grid = greener hydrogen.
        """
        if carbon_df.empty:
            st.markdown(
                f'<div style="text-align:center;padding:2rem;'
                f'color:{COLORS["text_muted"]};">'
                f'No carbon intensity data available for {region_short}.'
                f'</div>',
                unsafe_allow_html=True,
            )
            return

        fig_carbon = go.Figure()

        # Green zone (low carbon, 0–200 gCO₂eq/kWh)
        fig_carbon.add_trace(go.Scatter(
            x=[carbon_df["datetime"].iloc[0], carbon_df["datetime"].iloc[-1]],
            y=[200, 200], mode="lines", line=dict(width=0),
            showlegend=False, hoverinfo="skip",
        ))
        fig_carbon.add_trace(go.Scatter(
            x=[carbon_df["datetime"].iloc[0], carbon_df["datetime"].iloc[-1]],
            y=[0, 0], mode="lines", line=dict(width=0),
            fill="tonexty", fillcolor="rgba(63,185,80,0.08)",
            showlegend=False, hoverinfo="skip",
        ))

        # Carbon intensity line
        fig_carbon.add_trace(go.Scatter(
            x=carbon_df["datetime"], y=carbon_df["carbon_intensity"],
            mode="lines", name="Carbon Intensity",
            line=dict(color=COLORS["orange"], width=1.5),
            hovertemplate=(
                "<b>%{x|%a %d %b, %H:%M}</b><br>"
                "%{y:.0f} gCO₂eq/kWh<br><extra></extra>"
            ),
        ))

        fig_carbon.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color=COLORS["text_muted"], size=11),
            margin=dict(l=50, r=20, t=20, b=40),
            height=300,
            xaxis=dict(showgrid=False, linecolor=COLORS["border"],
                       tickfont=dict(color=COLORS["text_muted"], size=10)),
            yaxis=dict(title="gCO₂eq/kWh",
                       title_font=dict(color=COLORS["text_muted"], size=10),
                       gridcolor=COLORS["border_light"], gridwidth=0.5,
                       tickfont=dict(color=COLORS["text_muted"], size=10),
                       rangemode="tozero"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02,
                        xanchor="left", x=0, font=dict(size=10)),
            hovermode="x unified",
        )
        st.plotly_chart(fig_carbon, use_container_width=True, key="carbon_trend_chart")

    # Carbon KPI cards
    if not carbon_df.empty:
        latest_carbon = carbon_df["carbon_intensity"].iloc[-1]
        avg_carbon = carbon_df["carbon_intensity"].mean()
        min_carbon = carbon_df["carbon_intensity"].min()

        c1, c2, c3 = st.columns(3)
        with c1:
            metric_card(
                label="CURRENT",
                value=f"{latest_carbon:.0f}",
                subtitle="gCO₂eq/kWh",
                color=COLORS["green"] if latest_carbon < 400 else COLORS["red"],
            )
        with c2:
            metric_card(
                label=f"AVG ({carbon_range})",
                value=f"{avg_carbon:.0f}",
                subtitle="gCO₂eq/kWh",
                color=COLORS["text_primary"],
            )
        with c3:
            metric_card(
                label="CLEANEST HOUR",
                value=f"{min_carbon:.0f}",
                subtitle="gCO₂eq/kWh",
                color=COLORS["green"],
            )

    # Wrap carbon chart in a dashboard card
    dashboard_card(
        title=f"Carbon Intensity — {region_short} ({carbon_range})",
        content_func=draw_carbon_trend,
    )
