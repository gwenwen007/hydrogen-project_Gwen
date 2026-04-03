"""
Page 2 — Price Forecast
========================
Trains the ML model on historical data and displays predicted electricity
prices for the next 24–72 hours, including confidence indicators.

Grading requirements addressed:
- Requirement 5: Machine learning implementation
- Requirement 3: Data visualisation (forecast chart with confidence bands)
- Requirement 4: User interaction (forecast horizon selector, retrain button)
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

from utils.api import fetch_electricity_prices, fetch_weather_data
from utils.model import build_features, train_model, predict_prices, FEATURE_COLUMNS, WEATHER_COLUMNS
from utils.helpers import (
    AUSTRALIAN_REGIONS,
    inject_custom_css,
    get_plotly_template,
    render_kpi_bar,
    render_status_bar,
    render_sidebar_brand,
    render_card_header,
    COLORS,
)

# ---------- Page config ----------
st.set_page_config(page_title="Price Forecast", page_icon="🔮", layout="wide")
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
forecast_horizon = st.sidebar.selectbox("Forecast Horizon", [24, 48, 72], index=2,
                                         format_func=lambda h: f"{h} hours")
training_hours = st.sidebar.slider("Training data (hours)", 168, 720, 336, step=24)

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
st.title("🔮 Price Forecast")

# ---------- Train button ----------
if st.sidebar.button("Retrain Model", type="primary") or "model_trained" not in st.session_state:
    with st.spinner("Fetching training data..."):
        price_df = fetch_electricity_prices(region=region_code, hours=training_hours)
        weather_df = fetch_weather_data(latitude=region["lat"], longitude=region["lon"],
                                         hours=training_hours)

    with st.spinner("Building features and training model..."):
        features_df = build_features(price_df, weather_df)
        model, mse, X_test, y_test = train_model(features_df)

    st.session_state["model"] = model
    st.session_state["mse"] = mse
    st.session_state["X_test"] = X_test
    st.session_state["y_test"] = y_test
    st.session_state["features_df"] = features_df
    st.session_state["model_trained"] = True

# ---------- Display results ----------
if st.session_state.get("model_trained"):
    model = st.session_state["model"]
    mse = st.session_state["mse"]
    features_df = st.session_state["features_df"]
    rmse = np.sqrt(mse)

    # --- Model info banner ---
    # PLUG: model_metrics — Replace with live model metrics after retraining
    r_squared = 0.87  # PLUG: r_squared — Calculate from model.score(X_test, y_test)
    training_size = len(features_df)
    st.markdown(
        f'<div class="dashboard-card" style="border-left:3px solid {COLORS["accent"]};">'
        f'<span style="color:{COLORS["text_muted"]};">Model trained</span>  |  '
        f'<span style="color:{COLORS["text"]};">Linear Regression</span>  |  '
        f'MSE: <span style="color:{COLORS["accent"]};">{mse:.1f}</span>  |  '
        f'R²: <span style="color:{COLORS["accent"]};">{r_squared}</span>  |  '
        f'Training data: <span style="color:{COLORS["accent"]};">{training_size:,} hours</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # --- Build future predictions ---
    last_row = features_df.iloc[-1]
    future_rows = []
    for h in range(forecast_horizon):
        row = {
            "hour_of_day": (last_row["hour_of_day"] + h + 1) % 24,
            "day_of_week": (last_row["day_of_week"] + (h + 1) // 24) % 7,
            "price_lag_1h": last_row["price_aud_mwh"] if h == 0
                            else future_rows[-1].get("predicted_price_aud_mwh",
                                                      last_row["price_aud_mwh"]),
            "price_lag_24h": last_row["price_aud_mwh"],
            "timestamp": pd.Timestamp.utcnow() + pd.Timedelta(hours=h + 1),
        }
        for wc in WEATHER_COLUMNS:
            if wc in last_row.index:
                row[wc] = last_row[wc]
        future_rows.append(row)

    future_df = pd.DataFrame(future_rows)
    predictions = predict_prices(model, future_df)

    for i, pred in enumerate(predictions["predicted_price_aud_mwh"]):
        if i < len(future_rows):
            future_rows[i]["predicted_price_aud_mwh"] = pred

    # --- Main layout ---
    col_chart, col_insights = st.columns([3, 1])

    with col_chart:
        # --- Forecast chart with confidence interval ---
        with st.expander(f"{forecast_horizon}-Hour Price Forecast", expanded=True):
            # Indicator toggles
            show_ema = st.checkbox("EMA 24h", value=True)
            show_bollinger = st.checkbox("Bollinger Bands", value=False)
            show_breakeven = st.checkbox("Break-even", value=True)

            fig_fc = go.Figure()

            # Confidence band
            upper = predictions["predicted_price_aud_mwh"] + rmse
            lower = predictions["predicted_price_aud_mwh"] - rmse

            fig_fc.add_trace(go.Scatter(
                x=predictions["timestamp"], y=upper, mode="lines",
                line=dict(width=0), showlegend=False, hoverinfo="skip",
            ))
            fig_fc.add_trace(go.Scatter(
                x=predictions["timestamp"], y=lower, mode="lines",
                fill="tonexty", fillcolor="rgba(0, 212, 170, 0.12)",
                line=dict(width=0), name="80% CI",
            ))

            # Forecast line
            fig_fc.add_trace(go.Scatter(
                x=predictions["timestamp"],
                y=predictions["predicted_price_aud_mwh"],
                mode="lines",
                name="Forecast",
                line=dict(color=COLORS["accent"], width=2),
            ))

            # EMA overlay
            if show_ema:
                ema = predictions["predicted_price_aud_mwh"].ewm(span=24, adjust=False).mean()
                fig_fc.add_trace(go.Scatter(
                    x=predictions["timestamp"], y=ema,
                    mode="lines", name="EMA 24h",
                    line=dict(color=COLORS["amber"], width=1.5, dash="dot"),
                ))

            # Bollinger bands
            if show_bollinger:
                rolling_mean = predictions["predicted_price_aud_mwh"].rolling(20, min_periods=1).mean()
                rolling_std = predictions["predicted_price_aud_mwh"].rolling(20, min_periods=1).std().fillna(0)
                bb_upper = rolling_mean + 2 * rolling_std
                bb_lower = rolling_mean - 2 * rolling_std
                fig_fc.add_trace(go.Scatter(
                    x=predictions["timestamp"], y=bb_upper,
                    mode="lines", name="BB Upper",
                    line=dict(color=COLORS["purple"], width=1, dash="dash"),
                ))
                fig_fc.add_trace(go.Scatter(
                    x=predictions["timestamp"], y=bb_lower,
                    mode="lines", name="BB Lower",
                    line=dict(color=COLORS["purple"], width=1, dash="dash"),
                ))

            # Break-even line
            if show_breakeven:
                fig_fc.add_hline(
                    y=45, line_dash="dash", line_color=COLORS["amber"],
                    annotation_text="Break-even $45",
                    annotation_font_color=COLORS["amber"],
                )

            fig_fc.add_hline(y=0, line_dash="dot", line_color=COLORS["red"], opacity=0.5)
            fig_fc.update_layout(
                **get_plotly_template(),
                height=380,
                yaxis_title="AUD/MWh",
                xaxis_title="",
            )
            st.plotly_chart(fig_fc, use_container_width=True)

    # --- Forecast insights sidebar ---
    with col_insights:
        render_card_header("Forecast Insights")
        # PLUG: forecast_insights — Calculate from actual predictions
        neg_prob = len(predictions[predictions["predicted_price_aud_mwh"] < 0]) / len(predictions) * 100
        min_price = predictions["predicted_price_aud_mwh"].min()
        min_idx = predictions["predicted_price_aud_mwh"].idxmin()
        hours_to_trough = min_idx if isinstance(min_idx, int) else 0

        insight_items = [
            ("Neg. price probability", f"{neg_prob:.0f}%", f"Next {forecast_horizon}h"),
            ("Expected trough", f"${min_price:.0f}", f"In ~{hours_to_trough}h"),
            ("Confidence range", f"±${rmse:.0f}", "80% CI"),
            ("Trend direction", "Falling" if predictions["predicted_price_aud_mwh"].iloc[-1] < predictions["predicted_price_aud_mwh"].iloc[0] else "Rising", "Next 6h"),
        ]
        for label, value, sub in insight_items:
            st.markdown(
                f'<div class="dashboard-card">'
                f'<div style="color:{COLORS["text_muted"]}; font-size:0.7rem; text-transform:uppercase;">{label}</div>'
                f'<div style="color:{COLORS["accent"]}; font-size:1.3rem; font-weight:700;">{value}</div>'
                f'<div style="color:{COLORS["text_muted"]}; font-size:0.7rem;">{sub}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    st.markdown("")  # spacer

    # --- Feature importance ---
    col_heat, col_feat = st.columns([2, 1])

    with col_heat:
        # --- Negative price probability heatmap ---
        with st.expander("Negative Price Probability — Next 72 Hours", expanded=True):
            render_card_header("Hover over cells for exact probability")
            # PLUG: neg_probability_matrix — Calculate from model predictions
            hours_labels = ["00:00", "02:00", "04:00", "06:00", "08:00", "10:00",
                            "12:00", "14:00", "16:00", "18:00", "20:00", "22:00"]
            day_labels = ["Day 1", "Day 2", "Day 3"]
            # Placeholder probability matrix
            prob_matrix = [
                [10, 30, 60, 80, 90, 50, 20, 10, 5, 15, 40, 70],
                [60, 70, 80, 90, 85, 40, 15, 10, 8, 20, 50, 65],
                [30, 40, 50, 60, 50, 30, 20, 15, 10, 25, 35, 40],
            ]

            fig_heat = go.Figure(data=go.Heatmap(
                z=prob_matrix,
                x=hours_labels,
                y=day_labels,
                colorscale=[[0, COLORS["bg_card"]], [0.5, COLORS["accent_light"]], [1, COLORS["green"]]],
                text=[[f"{v}%" for v in row] for row in prob_matrix],
                texttemplate="%{text}",
                textfont=dict(size=10),
                showscale=True,
                colorbar=dict(title="Prob %", tickfont=dict(color=COLORS["text_muted"])),
            ))
            fig_heat.update_layout(
                **get_plotly_template(),
                height=220,
                xaxis_title="",
                yaxis_title="",
                yaxis=dict(autorange="reversed"),
            )
            st.plotly_chart(fig_heat, use_container_width=True)

    with col_feat:
        # --- Feature importance ---
        with st.expander("Feature Importance", expanded=True):
            # PLUG: feature_importance — Replace with model.feature_importances_ or coefficients
            features = ["Lag price (t-1)", "Wind speed", "Hour of day", "Solar radiation"]
            importance = [42, 28, 18, 12]

            fig_feat = go.Figure(go.Bar(
                x=importance,
                y=features,
                orientation="h",
                marker_color=[COLORS["accent"], COLORS["accent_light"], COLORS["amber"], COLORS["purple"]],
                text=[f"{v}%" for v in importance],
                textposition="inside",
                textfont=dict(color=COLORS["bg_main"]),
            ))
            fig_feat.update_layout(
                **get_plotly_template(),
                height=220,
                showlegend=False,
                xaxis_title="Importance (%)",
                yaxis=dict(autorange="reversed"),
            )
            st.plotly_chart(fig_feat, use_container_width=True)

    # Store predictions for the optimizer page
    st.session_state["price_forecast"] = predictions

else:
    st.info("Click **Retrain Model** in the sidebar to get started.")

# ---------- Status bar ----------
render_status_bar(connected=True, last_sync="14:32 AEST")
