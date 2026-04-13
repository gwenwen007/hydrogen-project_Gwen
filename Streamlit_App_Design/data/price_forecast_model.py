"""
price_forecast_model.py — Linear Regression for electricity price forecasting.

This is the ML component of the H2 Optimizer app.  It trains a
LinearRegression model on historical AEMO price data and produces
a 48-hour-ahead forecast.

The model learns the relationship:
    price ≈ f(hour_sin, hour_cos, dow_sin, dow_cos, month_sin, month_cos)

We use sine/cosine encoding for cyclical features so that the model
understands that hour 23 is close to hour 0, and December is close
to January.  This is standard feature engineering for time-series
data and dramatically improves prediction accuracy.

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


# =====================================================================
# FEATURE ENGINEERING — cyclical encoding
# =====================================================================

def _add_cyclical_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add sine/cosine encoded time features to a DataFrame.

    Why sine/cosine?  Hours and months are cyclical:
      - Hour 23 is close to hour 0 (both nighttime)
      - December (12) is close to January (1) (both summer in Australia)

    A raw integer (hour=0, hour=23) doesn't capture this — the model
    would think 0 and 23 are far apart.  Sine/cosine encoding places
    them on a circle so the model sees their true proximity.
    """
    df = df.copy()

    # Hour of day: cycle length = 24
    df["hour_sin"] = np.sin(2 * np.pi * df["timestamp"].dt.hour / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["timestamp"].dt.hour / 24)

    # Day of week: cycle length = 7
    df["dow_sin"] = np.sin(2 * np.pi * df["timestamp"].dt.dayofweek / 7)
    df["dow_cos"] = np.cos(2 * np.pi * df["timestamp"].dt.dayofweek / 7)

    # Month of year: cycle length = 12
    df["month_sin"] = np.sin(2 * np.pi * df["timestamp"].dt.month / 12)
    df["month_cos"] = np.cos(2 * np.pi * df["timestamp"].dt.month / 12)

    return df


# The 6 feature columns used by the model
FEATURE_COLS = ["hour_sin", "hour_cos", "dow_sin", "dow_cos", "month_sin", "month_cos"]


def run_forecast(region_abbr: str = "NSW", horizon_hours: int = 48) -> dict:
    """
    Train a LinearRegression on historical prices and forecast ahead.

    Steps:
      1. Load all historical hourly prices for the region
      2. Create cyclical features (sin/cos encoding)
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
    all_prices = load_prices(region_abbr)

    # Train on the last 90 days only (not the full year).
    # Reason: recent market conditions are more predictive of the near
    # future than prices from 6+ months ago.  This dramatically improves
    # accuracy (R²) compared to training on the full dataset.
    train_days = 90
    train_start = all_prices["timestamp"].max() - timedelta(days=train_days)
    prices_df = all_prices[all_prices["timestamp"] >= train_start].copy()

    # Use the last 7 days of history for the chart display
    display_days = 7
    display_start = prices_df["timestamp"].max() - timedelta(days=display_days)
    display_df = prices_df[prices_df["timestamp"] >= display_start].copy()

    # ── 2. Create cyclical features ──
    prices_df = _add_cyclical_features(prices_df)
    display_df = _add_cyclical_features(display_df)

    X_all = prices_df[FEATURE_COLS]        # features (last 90 days)
    y_all = prices_df["price_aud_mwh"]     # target

    # ── 3. Train the model ──
    # Split: train on first 80%, evaluate on last 20%
    # This ensures we test on data the model hasn't seen.
    split_idx = int(len(prices_df) * 0.8)
    X_train = X_all.iloc[:split_idx]
    y_train = y_all.iloc[:split_idx]

    model = LinearRegression()             # create model
    model.fit(X_train, y_train)            # train on 80% of data

    # ── 4. Generate forecast ──
    last_ts = prices_df["timestamp"].max()
    future_ts = [last_ts + timedelta(hours=i + 1) for i in range(horizon_hours)]
    future_df = pd.DataFrame({"timestamp": future_ts})
    future_df = _add_cyclical_features(future_df)

    # Predict future prices
    forecast_values = model.predict(future_df[FEATURE_COLS])

    # Predict on the display history (for the chart overlay)
    hist_predicted = model.predict(display_df[FEATURE_COLS])

    # ── 5. Build confidence interval ──
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

    # ── 7. Compute accuracy metrics on the held-out test set (last 20%) ──
    # This gives an honest measure of how well the model generalises.
    X_test = X_all.iloc[split_idx:]
    y_test = y_all.iloc[split_idx:]
    test_pred = model.predict(X_test)

    rmse = float(np.sqrt(mean_squared_error(y_test, test_pred)))
    mae = float(mean_absolute_error(y_test, test_pred))
    r2 = float(r2_score(y_test, test_pred))

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
