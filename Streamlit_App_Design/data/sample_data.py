"""
sample_data.py — Placeholder data for the H2 Optimizer Streamlit app.

This file provides hardcoded data for every page and component so the
front-end can be developed and tested without live API connections.

Once the API and ML code is ready, replace each function call with the
real data source.  The return formats are documented so the API / ML
team knows exactly what shape the front-end expects.

Usage in any page:
    from data.sample_data import get_spot_prices_7d, get_forecast, ...

Data flow in the real app:
    APIs (AEMO, Open-Meteo, ...) → download to CSV → ML reads CSV → front-end displays

This file simulates ALL stages of that pipeline so every team member
can work independently.
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


# =====================================================================
# HELPERS
# =====================================================================

def _hourly_timestamps(start: str, hours: int) -> list[datetime]:
    """Generate a list of hourly datetime objects."""
    base = datetime.fromisoformat(start)
    return [base + timedelta(hours=i) for i in range(hours)]


def _daily_timestamps(start: str, days: int) -> list[datetime]:
    base = datetime.fromisoformat(start)
    return [base + timedelta(days=i) for i in range(days)]


# =====================================================================
# 0. HISTORICAL CSV — THE CENTRAL DATA FILE
# =====================================================================
#
# In the real app, the API team downloads data into a CSV that looks
# exactly like what generate_historical_csv() produces.  The ML model
# reads this CSV as input.  The front-end reads it for display.
#
# Call generate_historical_csv() once to create the file, then use
# load_historical_csv() everywhere else.
# =====================================================================

def generate_historical_csv(
    filepath: str = "data/historical_nem_data.csv",
    days: int = 90,
    seed: int = 42,
) -> str:
    """
    Generate a realistic 90-day historical dataset and save it as CSV.
    This simulates what the API team's download scripts produce.

    The CSV has one row per hour with columns:
        timestamp, price_aud_mwh, demand_gw, solar_gw, wind_gw,
        temperature_c, cloud_cover_pct, wind_speed_kmh,
        solar_radiation_wm2, region

    Returns the filepath so you can confirm where it was saved.
    """
    np.random.seed(seed)
    hours = days * 24
    ts = _hourly_timestamps("2026-01-06T00:00:00", hours)
    h = np.arange(hours)
    hour_of_day = h % 24

    # --- Electricity price (AUD/MWh) ---
    # Realistic NEM pattern: daily cycle, weekly pattern, seasonal, noise, spikes
    daily = 20 * np.sin((hour_of_day - 6) * np.pi / 12)         # peak at noon
    weekly = 5 * np.sin(h * 2 * np.pi / 168)                     # weekly rhythm
    seasonal = 10 * np.sin(h * 2 * np.pi / (90 * 24))            # 90-day trend
    base = 42 + daily + weekly + seasonal
    noise = np.random.normal(0, 12, hours)
    # Occasional price spikes (5% of hours) and negative prices (8% of hours)
    spikes = np.where(np.random.random(hours) > 0.95,
                      np.random.uniform(50, 200, hours), 0)
    negatives = np.where(np.random.random(hours) > 0.92,
                         np.random.uniform(-20, -80, hours), 0)
    price = np.round(base + noise + spikes + negatives, 2)

    # --- Grid demand (GW) ---
    demand = 22 + 8 * np.sin((hour_of_day - 14) * np.pi / 12) \
             + np.random.normal(0, 1.5, hours)
    demand = np.round(np.maximum(12, demand), 2)

    # --- Solar generation (GW): bell curve during daytime ---
    solar = np.maximum(0, 5.0 * np.exp(-0.5 * ((hour_of_day - 12) / 3) ** 2))
    solar = np.round(solar * (0.8 + 0.4 * np.random.random(hours)), 2)

    # --- Wind generation (GW): semi-random with slow oscillation ---
    wind = 3.0 + 2.0 * np.sin(h * 2 * np.pi / 48) \
           + np.random.normal(0, 1.0, hours)
    wind = np.round(np.maximum(0, wind), 2)

    # --- Weather: temperature, cloud cover, wind speed, solar radiation ---
    temp = 20 + 10 * np.sin((hour_of_day - 6) * np.pi / 12) \
           + 5 * np.sin(h * 2 * np.pi / (90 * 24)) \
           + np.random.normal(0, 2, hours)
    temp = np.round(temp, 1)

    cloud = 35 + 20 * np.sin(h * 2 * np.pi / 48) + np.random.normal(0, 12, hours)
    cloud = np.clip(np.round(cloud, 0).astype(int), 0, 100)

    ws = 18 + 6 * np.sin(h * 2 * np.pi / 36) + np.random.normal(0, 4, hours)
    ws = np.round(np.maximum(0, ws), 1)

    sr = np.maximum(0, 900 * np.exp(-0.5 * ((hour_of_day - 12) / 3) ** 2)
                    * (1 - cloud / 250))
    sr = np.round(sr, 0).astype(int)

    df = pd.DataFrame({
        "timestamp":            ts,
        "price_aud_mwh":        price,
        "demand_gw":            demand,
        "solar_gw":             solar,
        "wind_gw":              wind,
        "temperature_c":        temp,
        "cloud_cover_pct":      cloud,
        "wind_speed_kmh":       ws,
        "solar_radiation_wm2":  sr,
        "region":               "NSW",   # default region
    })

    # Create directory if needed and save
    os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else ".", exist_ok=True)
    df.to_csv(filepath, index=False)
    return filepath


def load_historical_csv(filepath: str = "data/historical_nem_data.csv") -> pd.DataFrame:
    """
    Load the historical CSV.  This is the function every page should call
    instead of hitting an API directly.

    When the real APIs are connected, just make sure the CSV has the same
    columns and this function still works.
    """
    df = pd.read_csv(filepath, parse_dates=["timestamp"])
    return df


# =====================================================================
# 0b. LIVE / REAL-TIME DATA SIMULATION
# =====================================================================
#
# In the real app, AEMO publishes new prices every 5 minutes.
# These functions simulate that by treating the historical CSV as
# ground truth and returning slices of it as if they were "live."
#
# HOW IT WORKS:
#   - get_live_snapshot() returns the latest row + recent history
#   - The front-end calls it on page load (or with st.auto_refresh)
#   - When you connect real APIs, replace these functions with actual
#     API calls — the return format stays the same
# =====================================================================

def get_live_snapshot(
    filepath: str = "data/historical_nem_data.csv",
    lookback_hours: int = 168,
    simulated_now_idx: int = -1,
) -> dict:
    """
    Simulate a live data feed by returning a slice of historical data
    as if 'now' is the row at simulated_now_idx.

    Parameters:
        filepath:          path to the historical CSV
        lookback_hours:    how many hours of history to return
        simulated_now_idx: which row to treat as 'now' (-1 = last row)

    Returns dict with:
        current    — dict with the latest values (price, demand, etc.)
        history    — DataFrame of the last `lookback_hours` rows
        timestamp  — the 'now' timestamp
    """
    df = load_historical_csv(filepath)

    if simulated_now_idx == -1:
        simulated_now_idx = len(df) - 1

    # Slice the lookback window
    start_idx = max(0, simulated_now_idx - lookback_hours + 1)
    history = df.iloc[start_idx:simulated_now_idx + 1].copy().reset_index(drop=True)

    # Latest row as a dict
    latest = df.iloc[simulated_now_idx]
    prev = df.iloc[simulated_now_idx - 1] if simulated_now_idx > 0 else latest

    current = {
        "timestamp":       latest["timestamp"],
        "price_aud_mwh":   float(latest["price_aud_mwh"]),
        "price_change":    round(float(latest["price_aud_mwh"] - prev["price_aud_mwh"]), 2),
        "demand_gw":       float(latest["demand_gw"]),
        "solar_gw":        float(latest["solar_gw"]),
        "wind_gw":         float(latest["wind_gw"]),
        "temperature_c":   float(latest["temperature_c"]),
    }

    return {
        "current": current,
        "history": history,
        "timestamp": latest["timestamp"],
    }


# =====================================================================
# 1. MARKET OVERVIEW PAGE
# =====================================================================

# ---- 1a. KPI summary (top row of dashboard) ----

def get_market_kpis() -> dict:
    """
    Returns the 4 headline KPIs shown on the Market Overview top bar.
    """
    return {
        "current_price":  {"value": -12.40, "unit": "AUD/MWh", "delta": -51.10, "delta_pct": -134.2},
        "avg_24h":        {"value": 17.20,  "unit": "AUD/MWh", "delta": -8.30,  "delta_pct": -32.5},
        "avg_7d":         {"value": 34.60,  "unit": "AUD/MWh", "delta": 2.10,   "delta_pct": 6.5},
        "grid_demand":    {"value": 28.4,   "unit": "GW",      "delta": -1.2,   "delta_pct": -4.1},
    }


# ---- 1b. Spot price time-series (main chart + modal) ----

def get_spot_prices_7d() -> pd.DataFrame:
    """
    Hourly spot prices for the past 7 days (168 hours).
    Used in the main Market Overview chart and the indicator modal.
    """
    np.random.seed(42)
    ts = _hourly_timestamps("2026-04-01T00:00:00", 168)

    # Simulate realistic NEM prices: base pattern + noise + occasional spikes
    hours = np.arange(168)
    base = 35 + 20 * np.sin(hours * 2 * np.pi / 24)          # daily cycle
    weekly = 10 * np.sin(hours * 2 * np.pi / 168)             # weekly trend
    noise = np.random.normal(0, 12, 168)                       # random noise
    spikes = np.where(np.random.random(168) > 0.95, np.random.uniform(40, 120, 168), 0)
    negatives = np.where(np.random.random(168) > 0.92, np.random.uniform(-30, -80, 168), 0)
    prices = base + weekly + noise + spikes + negatives

    return pd.DataFrame({"timestamp": ts, "price_aud_mwh": np.round(prices, 2)})


def get_spot_prices_30d() -> pd.DataFrame:
    """Hourly spot prices for 30 days (720 hours)."""
    np.random.seed(123)
    ts = _hourly_timestamps("2026-03-08T00:00:00", 720)
    hours = np.arange(720)
    base = 38 + 22 * np.sin(hours * 2 * np.pi / 24)
    weekly = 8 * np.sin(hours * 2 * np.pi / 168)
    trend = -0.02 * hours                                      # slight downtrend
    noise = np.random.normal(0, 14, 720)
    prices = base + weekly + trend + noise
    return pd.DataFrame({"timestamp": ts, "price_aud_mwh": np.round(prices, 2)})


def get_spot_prices_90d() -> pd.DataFrame:
    """Daily average prices for 90 days."""
    np.random.seed(456)
    ts = _daily_timestamps("2026-01-06T00:00:00", 90)
    days = np.arange(90)
    base = 42 + 15 * np.sin(days * 2 * np.pi / 30)
    trend = -0.1 * days
    noise = np.random.normal(0, 8, 90)
    prices = base + trend + noise
    return pd.DataFrame({"timestamp": ts, "price_aud_mwh": np.round(prices, 2)})


def get_spot_prices_1y() -> pd.DataFrame:
    """Daily average prices for 365 days."""
    np.random.seed(789)
    ts = _daily_timestamps("2025-04-06T00:00:00", 365)
    days = np.arange(365)
    base = 45 + 20 * np.sin(days * 2 * np.pi / 365)           # seasonal
    monthly = 10 * np.sin(days * 2 * np.pi / 30)
    noise = np.random.normal(0, 10, 365)
    prices = base + monthly + noise
    return pd.DataFrame({"timestamp": ts, "price_aud_mwh": np.round(prices, 2)})


# ---- 1c. Technical indicators (for the modal) ----

def compute_ema(prices: pd.Series, span: int = 24) -> pd.Series:
    """Exponential Moving Average. Works on any price series."""
    return prices.ewm(span=span, adjust=False).mean().round(2)


def compute_bollinger_bands(prices: pd.Series, window: int = 20, num_std: int = 2) -> pd.DataFrame:
    """
    Bollinger Bands.
    Returns DataFrame with columns: bb_middle, bb_upper, bb_lower.
    """
    middle = prices.rolling(window=window).mean()
    std = prices.rolling(window=window).std()
    return pd.DataFrame({
        "bb_middle": middle.round(2),
        "bb_upper": (middle + num_std * std).round(2),
        "bb_lower": (middle - num_std * std).round(2),
    })


def compute_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """
    Relative Strength Index (0–100).
    Below 30 = oversold (cheap electricity, good time to produce).
    Above 70 = overbought (expensive, pause production).
    """
    delta = prices.diff()
    gain = delta.clip(lower=0).rolling(window=period).mean()
    loss = (-delta.clip(upper=0)).rolling(window=period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.round(2)


def compute_macd(prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """
    MACD indicator.
    Returns DataFrame with columns: macd_line, signal_line, histogram.
    """
    ema_fast = prices.ewm(span=fast, adjust=False).mean()
    ema_slow = prices.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return pd.DataFrame({
        "macd_line": macd_line.round(2),
        "signal_line": signal_line.round(2),
        "histogram": histogram.round(2),
    })


# ---- 1d. Renewable generation data ----

def get_renewable_generation_7d() -> pd.DataFrame:
    """
    Hourly renewable generation (GW) for 7 days.
    Simulates solar (daytime peak) + wind (semi-random).
    """
    np.random.seed(55)
    ts = _hourly_timestamps("2026-04-01T00:00:00", 168)
    hours = np.arange(168)
    hour_of_day = hours % 24

    # Solar: bell curve peaking at noon
    solar = np.maximum(0, 4.5 * np.exp(-0.5 * ((hour_of_day - 12) / 3) ** 2))
    # Wind: base + slow oscillation + noise
    wind = 2.5 + 1.5 * np.sin(hours * 2 * np.pi / 36) + np.random.normal(0, 0.8, 168)
    wind = np.maximum(0, wind)

    total = np.round(solar + wind, 2)
    return pd.DataFrame({
        "timestamp": ts,
        "solar_gw": np.round(solar, 2),
        "wind_gw": np.round(wind, 2),
        "total_gw": total,
    })


# ---- 1e. Regional price comparison ----

def get_regional_prices() -> pd.DataFrame:
    """
    Current prices across NEM regions.
    Used for the regional comparison card on Market Overview.
    """
    return pd.DataFrame({
        "region": ["NSW", "VIC", "QLD", "SA", "TAS"],
        "price_aud_mwh": [-12.40, 8.20, 22.50, -28.10, 45.30],
        "demand_gw": [8.2, 5.1, 6.8, 1.9, 1.2],
        "renewable_pct": [32, 41, 28, 58, 92],
    })


# ---- 1f. Market alerts / news ----

def get_market_alerts() -> list[dict]:
    """Mock market alerts for the news card."""
    return [
        {"time": "14:32", "severity": "warning", "message": "SA region negative pricing expected next 4 hours"},
        {"time": "13:15", "severity": "info",    "message": "Wind generation forecast upgraded for VIC (+1.2 GW)"},
        {"time": "12:01", "severity": "success", "message": "Optimal production window detected: 15:00–21:00 AEST"},
        {"time": "09:45", "severity": "error",   "message": "QLD interconnector constraint — prices may spike"},
        {"time": "08:30", "severity": "info",    "message": "BOM severe weather warning: potential solar curtailment SA"},
    ]


# ---- 1g. Price heatmap data (hourly x daily grid) ----

def get_price_heatmap_7d() -> pd.DataFrame:
    """
    Pivot table: rows = hour of day (0–23), columns = day name.
    Values = average price for that hour on that day.
    Used for the heatmap card on Market Overview.
    """
    df = get_spot_prices_7d()
    df["hour"] = df["timestamp"].dt.hour
    df["day"] = df["timestamp"].dt.strftime("%a")
    pivot = df.pivot_table(values="price_aud_mwh", index="hour", columns="day", aggfunc="mean")
    # Reorder columns Mon–Sun
    day_order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    pivot = pivot.reindex(columns=[d for d in day_order if d in pivot.columns])
    return pivot.round(2)


# =====================================================================
# 2. PRICE FORECAST PAGE
# =====================================================================

def get_forecast(model_name: str = "linear_regression", horizon_hours: int = 48) -> dict:
    """
    Returns forecast data in the format the front-end expects.

    Parameters:
        model_name: "linear_regression" | "random_forest" | "xgboost"
        horizon_hours: how many hours ahead to forecast

    Returns dict with keys:
        timestamps, actual, predicted, lower_bound, upper_bound, metrics
    """
    np.random.seed({"linear_regression": 100, "random_forest": 200, "xgboost": 300}.get(model_name, 100))

    # Historical (last 120 hours) + forecast
    hist_hours = 120
    total = hist_hours + horizon_hours
    ts = _hourly_timestamps("2026-03-31T00:00:00", total)
    hours = np.arange(total)

    # "Actual" prices (only for the historical portion)
    base = 38 + 18 * np.sin(hours * 2 * np.pi / 24)
    noise = np.random.normal(0, 10, total)
    actual = base + noise

    # "Predicted" — actual + model-specific bias and error
    error_scale = {"linear_regression": 8, "random_forest": 5, "xgboost": 4}.get(model_name, 8)
    pred_noise = np.random.normal(0, error_scale, total)
    predicted = base + pred_noise

    # Confidence interval widens into the future
    ci_base = {"linear_regression": 12, "random_forest": 8, "xgboost": 6}.get(model_name, 12)
    ci_expansion = np.concatenate([
        np.full(hist_hours, 1.0),
        np.linspace(1.0, 2.5, horizon_hours),
    ])
    ci = ci_base * ci_expansion
    lower = predicted - ci
    upper = predicted + ci

    # Metrics (computed on historical portion only)
    hist_actual = actual[:hist_hours]
    hist_pred = predicted[:hist_hours]
    residuals = hist_actual - hist_pred
    rmse = float(np.sqrt(np.mean(residuals ** 2)).round(2))
    mae = float(np.mean(np.abs(residuals)).round(2))
    ss_res = np.sum(residuals ** 2)
    ss_tot = np.sum((hist_actual - np.mean(hist_actual)) ** 2)
    r2 = float((1 - ss_res / ss_tot).round(3))

    return {
        "timestamps": ts,
        "actual": np.round(actual, 2).tolist(),
        "predicted": np.round(predicted, 2).tolist(),
        "lower_bound": np.round(lower, 2).tolist(),
        "upper_bound": np.round(upper, 2).tolist(),
        "hist_hours": hist_hours,            # index where forecast starts
        "model_name": model_name,
        "metrics": {
            "rmse": rmse,
            "mae": mae,
            "r2": r2,
            "horizon_hours": horizon_hours,
        },
    }


def get_feature_importance(model_name: str = "linear_regression") -> pd.DataFrame:
    """
    Feature importance scores for the forecast model.
    Used for the horizontal bar chart on the Price Forecast page.
    """
    features = {
        "linear_regression": [
            ("Hour of day",           0.28),
            ("Lagged price (t-1)",    0.22),
            ("Solar generation",      0.16),
            ("Wind generation",       0.12),
            ("Temperature",           0.08),
            ("Grid demand",           0.07),
            ("Day of week",           0.04),
            ("Interconnector flow",   0.03),
        ],
        "random_forest": [
            ("Lagged price (t-1)",    0.25),
            ("Hour of day",           0.20),
            ("Solar generation",      0.18),
            ("Wind generation",       0.14),
            ("Temperature",           0.09),
            ("Grid demand",           0.06),
            ("Interconnector flow",   0.05),
            ("Day of week",           0.03),
        ],
        "xgboost": [
            ("Lagged price (t-1)",    0.30),
            ("Solar generation",      0.19),
            ("Hour of day",           0.17),
            ("Wind generation",       0.13),
            ("Temperature",           0.08),
            ("Grid demand",           0.06),
            ("Day of week",           0.04),
            ("Interconnector flow",   0.03),
        ],
    }
    data = features.get(model_name, features["linear_regression"])
    return pd.DataFrame(data, columns=["feature", "importance"])


def get_available_models() -> list[dict]:
    """List of models the user can choose from in the dropdown."""
    return [
        {"id": "linear_regression", "label": "Linear Regression (Baseline)", "description": "Simple, fast, interpretable"},
        {"id": "random_forest",     "label": "Random Forest",               "description": "Better accuracy, slower"},
        {"id": "xgboost",           "label": "XGBoost",                     "description": "Best accuracy, most complex"},
    ]


# =====================================================================
# 3. PRODUCTION OPTIMIZER PAGE
# =====================================================================

def get_electrolyser_defaults() -> dict:
    """Default values for the optimizer input controls."""
    return {
        "capacity_mw": 10,
        "capacity_range": (1, 50),
        "breakeven_price": 45.0,
        "breakeven_range": (10.0, 120.0),
        "efficiency_kwh_per_kg": 55,
        "water_cost_per_kg": 0.05,
        "min_run_hours": 2,                # minimum continuous run time
    }


def get_optimised_schedule(
    breakeven: float = 45.0,
    capacity_mw: float = 10.0,
    horizon_hours: int = 168,
) -> pd.DataFrame:
    """
    Production schedule: for each hour, whether to produce or not.

    Returns DataFrame with columns:
        timestamp, price, produce (bool), h2_kg, cost_aud
    """
    prices_df = get_spot_prices_7d()
    prices_df = prices_df.head(horizon_hours)

    prices_df["produce"] = prices_df["price_aud_mwh"] < breakeven
    # H2 output: capacity (MW) × 1 hour × 1000 (kW/MW) / 55 (kWh/kg)
    kg_per_hour = capacity_mw * 1000 / 55
    prices_df["h2_kg"] = np.where(prices_df["produce"], round(kg_per_hour, 1), 0)
    prices_df["cost_aud"] = np.where(
        prices_df["produce"],
        np.round(prices_df["price_aud_mwh"] * capacity_mw, 2),
        0,
    )
    return prices_df


def get_optimizer_summary(
    breakeven: float = 45.0,
    capacity_mw: float = 10.0,
) -> dict:
    """
    Summary KPIs for the optimizer page.
    Compares optimised vs. naive (24/7) production.
    """
    schedule = get_optimised_schedule(breakeven, capacity_mw)
    total_hours = len(schedule)
    prod_hours = int(schedule["produce"].sum())

    optimised_cost = float(schedule["cost_aud"].sum())
    optimised_h2 = float(schedule["h2_kg"].sum())
    avg_price_during_prod = float(
        schedule.loc[schedule["produce"], "price_aud_mwh"].mean()
    ) if prod_hours > 0 else 0

    # Naive: run 24/7 at whatever the price is
    kg_per_hour = capacity_mw * 1000 / 55
    naive_cost = float((schedule["price_aud_mwh"] * capacity_mw).sum())
    naive_h2 = round(kg_per_hour * total_hours, 1)

    savings = naive_cost - optimised_cost
    savings_pct = (savings / abs(naive_cost) * 100) if naive_cost != 0 else 0

    return {
        "optimised": {
            "total_cost_aud":       round(optimised_cost, 2),
            "total_h2_kg":          round(optimised_h2, 1),
            "production_hours":     prod_hours,
            "avg_elec_price":       round(avg_price_during_prod, 2),
            "cost_per_kg":          round(optimised_cost / optimised_h2, 2) if optimised_h2 > 0 else 0,
        },
        "naive": {
            "total_cost_aud":       round(naive_cost, 2),
            "total_h2_kg":          round(naive_h2, 1),
            "production_hours":     total_hours,
            "avg_elec_price":       round(schedule["price_aud_mwh"].mean(), 2),
            "cost_per_kg":          round(naive_cost / naive_h2, 2) if naive_h2 > 0 else 0,
        },
        "savings": {
            "absolute_aud":         round(savings, 2),
            "percentage":           round(savings_pct, 1),
        },
    }


# =====================================================================
# 4. COST ANALYSIS PAGE
# =====================================================================

def get_cost_breakdown(electricity_cost: float = 18500.0) -> pd.DataFrame:
    """
    Cost breakdown for the pie / donut chart.
    electricity_cost is passed in from the optimizer output.
    """
    return pd.DataFrame({
        "category": [
            "Electricity",
            "Water",
            "Maintenance",
            "Labour",
            "Depreciation",
            "Other",
        ],
        "cost_aud": [
            round(electricity_cost, 2),
            420.00,
            1250.00,
            2800.00,
            3500.00,
            680.00,
        ],
    })


def get_historical_cost_trend() -> pd.DataFrame:
    """
    Monthly average H2 production cost over the past 12 months.
    Used for the cost trend line chart.
    """
    np.random.seed(321)
    months = pd.date_range("2025-05-01", periods=12, freq="MS")
    base = 5.2 + np.random.normal(0, 0.4, 12)
    # Seasonal: cheaper in spring/autumn (more renewables), expensive in summer/winter
    month_num = months.month
    seasonal = 0.8 * np.sin((month_num - 4) * 2 * np.pi / 12)
    cost_per_kg = np.round(base + seasonal, 2)

    return pd.DataFrame({
        "month": months,
        "cost_per_kg_aud": cost_per_kg,
        "volume_kg": np.round(np.random.uniform(25000, 35000, 12), 0).astype(int),
    })


def get_sensitivity_analysis(
    base_cost_per_kg: float = 4.80,
) -> pd.DataFrame:
    """
    How H2 cost changes if electricity price moves by -20% to +20%.
    Used for the sensitivity table / chart on Cost Analysis.
    """
    # Electricity is roughly 65% of total H2 cost
    elec_share = 0.65
    scenarios = [-20, -10, -5, 0, 5, 10, 20]
    rows = []
    for pct in scenarios:
        elec_factor = 1 + pct / 100
        new_cost = base_cost_per_kg * (elec_share * elec_factor + (1 - elec_share))
        rows.append({
            "price_change_pct": pct,
            "h2_cost_per_kg": round(new_cost, 2),
            "change_vs_base": round(new_cost - base_cost_per_kg, 2),
        })
    return pd.DataFrame(rows)


def get_export_data() -> pd.DataFrame:
    """
    Comprehensive table for the CSV download button.
    Combines prices, schedule, and costs into one exportable sheet.
    """
    schedule = get_optimised_schedule()
    renewables = get_renewable_generation_7d()

    export = schedule[["timestamp", "price_aud_mwh", "produce", "h2_kg", "cost_aud"]].copy()
    export = export.merge(
        renewables[["timestamp", "solar_gw", "wind_gw", "total_gw"]],
        on="timestamp",
        how="left",
    )
    export["cumulative_h2_kg"] = export["h2_kg"].cumsum().round(1)
    export["cumulative_cost_aud"] = export["cost_aud"].cumsum().round(2)
    return export


# =====================================================================
# 5. WEATHER DATA (from Open-Meteo API — placeholder)
# =====================================================================

def get_weather_forecast() -> pd.DataFrame:
    """
    48-hour weather forecast used as ML model input.
    Simulates what the Open-Meteo API returns.
    """
    np.random.seed(77)
    ts = _hourly_timestamps("2026-04-06T00:00:00", 48)
    hours = np.arange(48)
    hour_of_day = hours % 24

    temp = 22 + 8 * np.sin((hour_of_day - 6) * np.pi / 12) + np.random.normal(0, 1.5, 48)
    cloud = 30 + 25 * np.sin(hours * 2 * np.pi / 36) + np.random.normal(0, 10, 48)
    cloud = np.clip(cloud, 0, 100)
    wind_speed = 15 + 8 * np.sin(hours * 2 * np.pi / 24) + np.random.normal(0, 3, 48)
    wind_speed = np.maximum(0, wind_speed)
    solar_radiation = np.maximum(0, 800 * np.exp(-0.5 * ((hour_of_day - 12) / 3) ** 2) * (1 - cloud / 200))

    return pd.DataFrame({
        "timestamp": ts,
        "temperature_c": np.round(temp, 1),
        "cloud_cover_pct": np.round(cloud, 0).astype(int),
        "wind_speed_kmh": np.round(wind_speed, 1),
        "solar_radiation_wm2": np.round(solar_radiation, 0).astype(int),
    })


# =====================================================================
# 6. INDICATOR MODAL — PRE-COMPUTED CONVENIENCE FUNCTIONS
# =====================================================================

def get_indicator_modal_data(timeframe: str = "7d") -> dict:
    """
    All-in-one function that returns everything needed for the
    indicator modal popup on the Market Overview page.

    Core indicators (recommended to keep):
        - EMA:             trend direction, trivial to compute
        - Bollinger Bands: volatility / price range
        - RSI:             identifies cheap electricity (oversold)

    Optional (only computed if you have spare time / extra data):
        - MACD:            momentum — less meaningful for hourly electricity
        - Renewable Gen:   requires a separate data source (AEMO generation)

    Parameters:
        timeframe: "7d" | "30d" | "90d" | "1y"

    Returns dict with:
        prices_df, ema, bollinger, rsi, stats
        (macd and renewables are still available but not computed by default)
    """
    # Pick the right price series
    price_funcs = {
        "7d":  get_spot_prices_7d,
        "30d": get_spot_prices_30d,
        "90d": get_spot_prices_90d,
        "1y":  get_spot_prices_1y,
    }
    prices_df = price_funcs.get(timeframe, get_spot_prices_7d)()
    prices = prices_df["price_aud_mwh"]

    # --- Core indicators (always computed) ---
    ema = compute_ema(prices, span=24)
    bb = compute_bollinger_bands(prices, window=20, num_std=2)
    rsi = compute_rsi(prices, period=14)

    # --- Current stats ---
    latest = prices.iloc[-1]
    prev = prices.iloc[-2] if len(prices) > 1 else latest
    latest_ema = ema.iloc[-1]
    latest_rsi = rsi.iloc[-1] if not np.isnan(rsi.iloc[-1]) else 50.0
    bb_pct_b = 0.0
    if not np.isnan(bb["bb_upper"].iloc[-1]) and (bb["bb_upper"].iloc[-1] - bb["bb_lower"].iloc[-1]) != 0:
        bb_pct_b = round((latest - bb["bb_lower"].iloc[-1]) / (bb["bb_upper"].iloc[-1] - bb["bb_lower"].iloc[-1]), 2)
    vol = round(float(prices.tail(24).std()), 1) if len(prices) >= 24 else 0

    # Production signal (based on 3 core indicators only)
    breakeven = 45.0
    signal = "PRODUCE" if latest < breakeven else "HOLD"
    signal_strength = sum([
        latest < breakeven,         # price below break-even
        latest < latest_ema,        # price below trend (EMA)
        latest_rsi < 40,            # RSI says oversold = cheap
    ])

    stats = {
        "current_price":  round(float(latest), 2),
        "change_24h":     round(float(latest - prev), 2),
        "ema_24h":        round(float(latest_ema), 2),
        "bb_pct_b":       bb_pct_b,
        "rsi_14":         round(float(latest_rsi), 1),
        "volatility":     vol,
        "signal":         signal,
        "signal_strength": f"{signal_strength}/3",
        "breakeven":      breakeven,
    }

    return {
        "prices_df": prices_df,
        "ema": ema,
        "bollinger": bb,
        "rsi": rsi,
        "stats": stats,
    }


def get_indicator_modal_data_extended(timeframe: str = "7d") -> dict:
    """
    Extended version that also computes MACD and loads renewable data.
    Only use this if your team decides to include these optional indicators.
    """
    base = get_indicator_modal_data(timeframe)
    prices = base["prices_df"]["price_aud_mwh"]
    base["macd"] = compute_macd(prices)
    base["renewables"] = get_renewable_generation_7d() if timeframe == "7d" else None
    return base


# =====================================================================
# QUICK TEST
# =====================================================================

if __name__ == "__main__":
    print("=== Testing sample_data.py ===\n")

    # --- Historical CSV ---
    csv_path = generate_historical_csv("data/historical_nem_data.csv", days=90)
    print(f"Historical CSV saved to: {csv_path}")
    hist = load_historical_csv(csv_path)
    print(f"  Shape: {hist.shape}  Columns: {list(hist.columns)}")
    print(f"  Date range: {hist['timestamp'].iloc[0]} to {hist['timestamp'].iloc[-1]}")

    # --- Live snapshot ---
    snap = get_live_snapshot(csv_path, lookback_hours=168)
    print(f"Live snapshot: price={snap['current']['price_aud_mwh']}, "
          f"history={len(snap['history'])} rows")

    # --- Page-specific data ---
    print(f"\nMarket KPIs: {get_market_kpis()['current_price']}")
    print(f"Spot 7d shape: {get_spot_prices_7d().shape}")
    print(f"Spot 30d shape: {get_spot_prices_30d().shape}")
    print(f"Forecast keys: {list(get_forecast().keys())}")
    print(f"Feature importance (LR): {len(get_feature_importance())} features")
    print(f"Optimiser schedule shape: {get_optimised_schedule().shape}")
    print(f"Optimizer summary savings: {get_optimizer_summary()['savings']}")
    print(f"Cost breakdown: {len(get_cost_breakdown())} categories")
    print(f"Historical cost trend: {len(get_historical_cost_trend())} months")
    print(f"Sensitivity: {len(get_sensitivity_analysis())} scenarios")
    print(f"Weather forecast shape: {get_weather_forecast().shape}")
    print(f"Export data shape: {get_export_data().shape}")

    # --- Indicator modal (core: EMA + BB + RSI) ---
    modal = get_indicator_modal_data("7d")
    print(f"\nModal (core): signal={modal['stats']['signal']}, "
          f"strength={modal['stats']['signal_strength']}, "
          f"RSI={modal['stats']['rsi_14']}")
    print(f"  Keys: {list(modal.keys())}")

    # --- Extended modal (+ MACD + Renewable) ---
    ext = get_indicator_modal_data_extended("7d")
    print(f"Modal (extended): has MACD={ext['macd'] is not None}, "
          f"has renewables={ext['renewables'] is not None}")

    print("\nAll tests passed.")
