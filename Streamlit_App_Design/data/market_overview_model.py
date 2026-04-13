"""
market_overview_model.py — Real-data functions for the Market Overview page.

Replaces the hardcoded sample data with calculations based on real
AEMO prices (historical CSVs + live 7-day API).  The technical
indicator functions (EMA, Bollinger Bands, RSI) are kept here as
well — they are pure math applied to whatever price series we load.

The News/Alerts function is NOT included here because the news API
is not yet connected.  market_overview.py will keep importing
get_market_alerts() from sample_data.py for now.

Usage:
    from data.market_overview_model import (
        get_market_kpis,
        get_spot_prices,
        get_indicator_modal_data,
        get_price_heatmap,
        get_regional_prices,
    )
"""

import numpy as np
import pandas as pd

# Real price data — includes both historical AEMO CSVs and live 7-day API
from data.electricity_prices_loader import load_prices


# =====================================================================
# REGION CODES
# =====================================================================
# All five NEM regions (Western Australia is not part of the NEM)

ALL_REGIONS = ["NSW", "VIC", "QLD", "SA", "TAS"]


# =====================================================================
# TECHNICAL INDICATORS
# =====================================================================
# These are pure mathematical functions applied to any price series.
# They were previously in sample_data.py — same logic, just moved here.

def compute_ema(prices: pd.Series, span: int = 24) -> pd.Series:
    """
    Exponential Moving Average.

    Smooths the price series to show the underlying trend direction.
    A span of 24 = 24-hour EMA (one-day trend for hourly data).
    """
    return prices.ewm(span=span, adjust=False).mean().round(2)


def compute_bollinger_bands(
    prices: pd.Series, window: int = 20, num_std: int = 2
) -> pd.DataFrame:
    """
    Bollinger Bands — volatility envelope around a moving average.

    Returns DataFrame with columns: bb_middle, bb_upper, bb_lower.
    When price breaks below the lower band, electricity is unusually
    cheap.  When it breaks above the upper band, it's unusually expensive.
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

    Below 30 = oversold (cheap electricity, good time to produce H₂).
    Above 70 = overbought (expensive, pause production).
    """
    delta = prices.diff()
    gain = delta.clip(lower=0).rolling(window=period).mean()
    loss = (-delta.clip(upper=0)).rolling(window=period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.round(2)


# =====================================================================
# KPI ROW — Four headline numbers
# =====================================================================

def get_market_kpis(region_abbr: str = "NSW") -> dict:
    """
    Compute the 4 headline KPIs from real AEMO price data.

    Returns a dict matching the format the page expects:
        current_price  → latest hourly price
        avg_24h        → average of last 24 hours, delta vs prior 24h
        avg_7d         → average of last 7 days, delta vs prior 7d
        grid_demand    → latest hourly demand in GW

    Each sub-dict has: value, unit, delta, delta_pct
    """
    df = load_prices(region_abbr)

    if df.empty:
        # Fallback if no data at all
        _zero = {"value": 0, "unit": "AUD/MWh", "delta": 0, "delta_pct": 0}
        return {
            "current_price": _zero,
            "avg_24h": _zero,
            "avg_7d": _zero,
            "grid_demand": {"value": 0, "unit": "GW", "delta": 0, "delta_pct": 0},
        }

    # ── Current price: latest hour in the dataset ──
    current = float(df["price_aud_mwh"].iloc[-1])
    prev = float(df["price_aud_mwh"].iloc[-2]) if len(df) > 1 else current
    curr_delta = round(current - prev, 2)
    curr_pct = round((curr_delta / abs(prev)) * 100, 1) if prev != 0 else 0

    # ── 24-hour average and its change vs the prior 24h ──
    last_24h = df.tail(24)["price_aud_mwh"]
    prior_24h = df.iloc[-48:-24]["price_aud_mwh"] if len(df) >= 48 else last_24h
    avg_24 = round(float(last_24h.mean()), 2)
    avg_24_prev = round(float(prior_24h.mean()), 2)
    avg_24_delta = round(avg_24 - avg_24_prev, 2)
    avg_24_pct = round((avg_24_delta / abs(avg_24_prev)) * 100, 1) if avg_24_prev != 0 else 0

    # ── 7-day average and its change vs the prior 7 days ──
    last_7d = df.tail(168)["price_aud_mwh"]
    prior_7d = df.iloc[-336:-168]["price_aud_mwh"] if len(df) >= 336 else last_7d
    avg_7d = round(float(last_7d.mean()), 2)
    avg_7d_prev = round(float(prior_7d.mean()), 2)
    avg_7d_delta = round(avg_7d - avg_7d_prev, 2)
    avg_7d_pct = round((avg_7d_delta / abs(avg_7d_prev)) * 100, 1) if avg_7d_prev != 0 else 0

    # ── Grid demand: latest hour ──
    # demand_gw may be NaN if the row came from the live API CSV
    demand_val = df["demand_gw"].iloc[-1]
    if pd.isna(demand_val):
        # Fall back to most recent non-NaN demand value
        valid_demand = df["demand_gw"].dropna()
        demand_val = float(valid_demand.iloc[-1]) if not valid_demand.empty else 0
    else:
        demand_val = float(demand_val)

    # Demand change vs 24h ago
    if len(df) >= 25:
        prev_demand = df["demand_gw"].iloc[-25]
        if pd.isna(prev_demand):
            valid_prev = df["demand_gw"].iloc[:-24].dropna()
            prev_demand = float(valid_prev.iloc[-1]) if not valid_prev.empty else demand_val
        else:
            prev_demand = float(prev_demand)
    else:
        prev_demand = demand_val

    demand_delta_pct = round(
        ((demand_val - prev_demand) / abs(prev_demand)) * 100, 1
    ) if prev_demand != 0 else 0

    return {
        "current_price": {
            "value": current, "unit": "AUD/MWh",
            "delta": curr_delta, "delta_pct": curr_pct,
        },
        "avg_24h": {
            "value": avg_24, "unit": "AUD/MWh",
            "delta": avg_24_delta, "delta_pct": avg_24_pct,
        },
        "avg_7d": {
            "value": avg_7d, "unit": "AUD/MWh",
            "delta": avg_7d_delta, "delta_pct": avg_7d_pct,
        },
        "grid_demand": {
            "value": round(demand_val, 1), "unit": "GW",
            "delta": round(demand_val - prev_demand, 1),
            "delta_pct": demand_delta_pct,
        },
    }


# =====================================================================
# SPOT PRICE TIME SERIES
# =====================================================================

def get_spot_prices(
    region_abbr: str = "NSW",
    timeframe: str = "7d",
) -> pd.DataFrame:
    """
    Load real spot prices for the selected timeframe.

    For 7d and 30d we return hourly data.
    For 90d and 1y we aggregate to daily averages (keeps charts fast).

    Parameters:
        region_abbr: NEM region abbreviation
        timeframe:   "7d" | "30d" | "90d" | "1y"

    Returns DataFrame with columns:
        timestamp      (datetime)
        price_aud_mwh  (float)
    """
    df = load_prices(region_abbr)

    if df.empty:
        return pd.DataFrame(columns=["timestamp", "price_aud_mwh"])

    # Map timeframe to number of hours to keep
    hours_map = {"24h": 24, "48h": 48, "7d": 168, "30d": 720, "90d": 2160, "1y": 8760}
    hours = hours_map.get(timeframe, 168)

    # Take the most recent N hours
    sliced = df.tail(hours)[["timestamp", "price_aud_mwh"]].copy()

    # For longer ranges, aggregate to daily averages
    if timeframe in ("90d", "1y"):
        sliced["date"] = sliced["timestamp"].dt.date
        daily = sliced.groupby("date").agg(
            price_aud_mwh=("price_aud_mwh", "mean"),
        ).reset_index()
        daily["timestamp"] = pd.to_datetime(daily["date"])
        daily.drop(columns=["date"], inplace=True)
        daily["price_aud_mwh"] = daily["price_aud_mwh"].round(2)
        return daily

    return sliced.reset_index(drop=True)


# =====================================================================
# INDICATOR MODAL — All-in-one data + indicators
# =====================================================================

def get_indicator_modal_data(
    region_abbr: str = "NSW",
    timeframe: str = "7d",
) -> dict:
    """
    Everything the indicator modal needs: prices + technical indicators.

    Parameters:
        region_abbr: NEM region
        timeframe:   "7d" | "30d" | "90d" | "1y"

    Returns dict with:
        prices_df  — DataFrame(timestamp, price_aud_mwh)
        ema        — EMA series (same length as prices)
        bollinger  — DataFrame(bb_upper, bb_lower, bb_middle)
        rsi        — RSI series (0–100)
        stats      — dict with current_price, signal, etc.
    """
    prices_df = get_spot_prices(region_abbr, timeframe)
    prices = prices_df["price_aud_mwh"]

    # ── Compute core indicators ──
    ema = compute_ema(prices, span=24)
    bb = compute_bollinger_bands(prices, window=20, num_std=2)
    rsi = compute_rsi(prices, period=14)

    # ── Current stats ──
    latest = float(prices.iloc[-1])
    prev = float(prices.iloc[-2]) if len(prices) > 1 else latest
    latest_ema = float(ema.iloc[-1])
    latest_rsi = float(rsi.iloc[-1]) if not np.isnan(rsi.iloc[-1]) else 50.0

    # Bollinger %B — where the price sits relative to the bands
    bb_pct_b = 0.0
    bb_upper_val = bb["bb_upper"].iloc[-1]
    bb_lower_val = bb["bb_lower"].iloc[-1]
    if not np.isnan(bb_upper_val) and (bb_upper_val - bb_lower_val) != 0:
        bb_pct_b = round(
            (latest - bb_lower_val) / (bb_upper_val - bb_lower_val), 2
        )

    # 24-hour volatility (standard deviation of last 24 data points)
    vol = round(float(prices.tail(24).std()), 1) if len(prices) >= 24 else 0

    # Production signal based on 3 core indicators
    breakeven = 45.0
    signal = "PRODUCE" if latest < breakeven else "HOLD"
    signal_strength = sum([
        latest < breakeven,       # price below break-even
        latest < latest_ema,      # price below trend (EMA)
        latest_rsi < 40,          # RSI says oversold = cheap
    ])

    stats = {
        "current_price": round(latest, 2),
        "change_24h":    round(latest - prev, 2),
        "ema_24h":       round(latest_ema, 2),
        "bb_pct_b":      bb_pct_b,
        "rsi_14":        round(latest_rsi, 1),
        "volatility":    vol,
        "signal":        signal,
        "signal_strength": f"{signal_strength}/3",
        "breakeven":     breakeven,
    }

    return {
        "prices_df": prices_df,
        "ema": ema,
        "bollinger": bb,
        "rsi": rsi,
        "stats": stats,
    }


# =====================================================================
# PRICE HEATMAP — Hour of day × Day of week
# =====================================================================

def get_price_heatmap(region_abbr: str = "NSW") -> pd.DataFrame:
    """
    Pivot table of average price by hour-of-day × day-of-week.

    Uses the last 7 days of real hourly data.  Rows = hour (0–23),
    columns = day name (Mon–Sun).

    Returns a pivot DataFrame suitable for px.imshow().
    """
    df = load_prices(region_abbr)

    if df.empty:
        return pd.DataFrame()

    # Take last 7 days of hourly data
    recent = df.tail(168).copy()
    recent["hour"] = recent["timestamp"].dt.hour
    recent["day"] = recent["timestamp"].dt.strftime("%a")

    # Pivot: rows = hour, columns = day
    pivot = recent.pivot_table(
        values="price_aud_mwh",
        index="hour",
        columns="day",
        aggfunc="mean",
    )

    # Reorder columns Mon–Sun
    day_order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    pivot = pivot.reindex(columns=[d for d in day_order if d in pivot.columns])

    return pivot.round(2)


# =====================================================================
# REGIONAL PRICE COMPARISON
# =====================================================================

def get_regional_prices() -> pd.DataFrame:
    """
    Current spot prices across all 5 NEM regions.

    Loads the latest hourly price for each region from real data.
    Returns DataFrame with columns: region, price_aud_mwh, demand_gw

    If a region has no data, it is excluded from the result.
    """
    rows = []
    for rgn in ALL_REGIONS:
        df = load_prices(rgn)
        if df.empty:
            continue

        latest_price = float(df["price_aud_mwh"].iloc[-1])

        # Demand may be NaN for live-API rows
        latest_demand = df["demand_gw"].iloc[-1]
        if pd.isna(latest_demand):
            valid = df["demand_gw"].dropna()
            latest_demand = float(valid.iloc[-1]) if not valid.empty else 0
        else:
            latest_demand = float(latest_demand)

        rows.append({
            "region": rgn,
            "price_aud_mwh": round(latest_price, 2),
            "demand_gw": round(latest_demand, 1),
        })

    return pd.DataFrame(rows)
