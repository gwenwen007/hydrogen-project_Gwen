"""
price_forecast_model.py — Simple Linear Regression for electricity price forecasting.

This is the ML component of the H2 Optimizer app.  It trains a
LinearRegression model on historical AEMO price data and produces
a 48-hour-ahead forecast.

The model learns the relationship:
    price ≈ f(hour_of_day, day_of_week)

That is: "on average, what does electricity cost at 3 PM on a
Tuesday?"  This captures the daily price cycle (cheap at night,
expensive in the evening) and weekly patterns (weekdays vs weekends).

It's deliberately simple — our supervisor said ~6 lines of core ML
code is enough for a "Fundamentals of Computer Science" course.

Usage:
    from data.price_forecast_model import run_forecast
    result = run_forecast(region_abbr="NSW", horizon_hours=48)
"""

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from datetime import timedelta

# Import our real data loader
from data.electricity_prices_loader import load_prices


def run_forecast(region_abbr: str = "NSW", horizon_hours: int = 48) -> dict:
    """
    Train a LinearRegression on historical prices and forecast ahead.

    Steps:
      1. Load all historical hourly prices for the region
      2. Create features: hour_of_day, day_of_week
      3. Train LinearRegression on all data
      4. Generate future timestamps and predict their prices
      5. Compute accuracy metrics on the last 100 hours of history

    Parameters:
        region_abbr:   "NSW", "VIC", "QLD", "SA", or "TAS"
        horizon_hours: how many hours to forecast (default 48)

    Returns dict with keys:
        timestamps   — list of datetime objects (history + forecast)
        actual       — list of floats (historical prices, NaN for forecast)
        predicted    — list of floats (model predictions for full range)
        lower_bound  — list of floats (confidence interval lower)
        upper_bound  — list of floats (confidence interval upper)
        hist_hours   — int (number of historical data points)
        metrics      — dict with rmse, mae, r2, horizon_hours
    """

    # ── 1. Load historical prices ──
    # This reads all AEMO CSVs and returns hourly-averaged data
    prices_df = load_prices(region_abbr)

    # Use the last 30 days of history for the chart display
    # (showing all 12 months would make the chart unreadable)
    display_days = 30
    display_start = prices_df["timestamp"].max() - timedelta(days=display_days)
    display_df = prices_df[prices_df["timestamp"] >= display_start].copy()

    # ── 2. Create features for the ML model ──
    # These are the only two inputs the model needs:
    #   hour_of_day: 0–23 (captures daily price cycle)
    #   day_of_week: 0–6  (captures weekday vs weekend pattern)
    prices_df["hour"] = prices_df["timestamp"].dt.hour
    prices_df["dayofweek"] = prices_df["timestamp"].dt.dayofweek

    X_all = prices_df[["hour", "dayofweek"]]       # features
    y_all = prices_df["price_aud_mwh"]              # target

    # ── 3. Train the model ──
    # This is the core ML — literally 3 lines of scikit-learn:
    model = LinearRegression()                      # create model
    model.fit(X_all, y_all)                         # train on all data

    # ── 4. Generate forecast ──
    # Create future timestamps starting from the last known hour
    last_ts = prices_df["timestamp"].max()
    future_ts = [last_ts + timedelta(hours=i + 1) for i in range(horizon_hours)]
    future_df = pd.DataFrame({"timestamp": future_ts})
    future_df["hour"] = future_df["timestamp"].dt.hour
    future_df["dayofweek"] = future_df["timestamp"].dt.dayofweek

    # Predict future prices
    forecast_values = model.predict(future_df[["hour", "dayofweek"]])

    # Also predict on the display history (for the chart overlay)
    display_df = display_df.copy()
    display_df["hour"] = display_df["timestamp"].dt.hour
    display_df["dayofweek"] = display_df["timestamp"].dt.dayofweek
    hist_predicted = model.predict(display_df[["hour", "dayofweek"]])

    # ── 5. Build confidence interval ──
    # Use the historical residuals (prediction errors) to estimate
    # how uncertain the forecast is.  The interval widens over time.
    hist_residuals = display_df["price_aud_mwh"].values - hist_predicted
    residual_std = float(np.std(hist_residuals))

    # Historical confidence: constant width based on residual spread
    hist_lower = hist_predicted - 1.96 * residual_std
    hist_upper = hist_predicted + 1.96 * residual_std

    # Forecast confidence: widens linearly into the future
    expansion = np.linspace(1.0, 2.5, horizon_hours)
    forecast_lower = forecast_values - 1.96 * residual_std * expansion
    forecast_upper = forecast_values + 1.96 * residual_std * expansion

    # ── 6. Combine into output format ──
    all_timestamps = list(display_df["timestamp"]) + future_ts
    all_actual = list(display_df["price_aud_mwh"]) + [float("nan")] * horizon_hours
    all_predicted = list(hist_predicted) + list(forecast_values)
    all_lower = list(hist_lower) + list(forecast_lower)
    all_upper = list(hist_upper) + list(forecast_upper)
    hist_count = len(display_df)

    # ── 7. Compute accuracy metrics on the last 100 hours ──
    eval_n = min(100, len(display_df))
    eval_actual = display_df["price_aud_mwh"].values[-eval_n:]
    eval_pred = hist_predicted[-eval_n:]

    rmse = float(np.sqrt(mean_squared_error(eval_actual, eval_pred)))
    mae = float(mean_absolute_error(eval_actual, eval_pred))
    r2 = float(r2_score(eval_actual, eval_pred))

    return {
        "timestamps":   all_timestamps,
        "actual":       [round(float(v), 2) if not np.isnan(v) else None for v in all_actual],
        "predicted":    [round(float(v), 2) for v in all_predicted],
        "lower_bound":  [round(float(v), 2) for v in all_lower],
        "upper_bound":  [round(float(v), 2) for v in all_upper],
        "hist_hours":   hist_count,
        "metrics": {
            "rmse": round(rmse, 2),
            "mae": round(mae, 2),
            "r2": round(r2, 3),
            "horizon_hours": horizon_hours,
        },
    }
