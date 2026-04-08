"""
production_optimizer_model.py — Production schedule optimizer using real data.

This module combines:
  - Real historical AEMO prices (from electricity_prices_loader.py)
  - ML-forecasted future prices (from price_forecast_model.py)

It produces an optimal production schedule: for each hour, if the
electricity price is below the user's break-even threshold → produce
hydrogen.  Otherwise → hold.

The optimizer then compares "optimised" vs "naive 24/7" to show
how much money the scheduling saves.

Usage:
    from data.production_optimizer_model import (
        get_electrolyser_defaults,
        get_optimised_schedule,
        get_optimizer_summary,
    )
"""

import numpy as np
import pandas as pd
from datetime import timedelta

# Real data sources
from data.electricity_prices_loader import load_prices
from data.price_forecast_model import run_forecast


# =====================================================================
# ELECTROLYSER CONFIGURATION DEFAULTS
# =====================================================================
# These are config values for the UI sliders — not API data.
# They can stay hardcoded because they describe the physical
# electrolyser, not market conditions.

def get_electrolyser_defaults() -> dict:
    """
    Default values for the optimizer input controls.

    Returns a dict with:
        capacity_mw        — default electrolyser size in megawatts
        capacity_range     — (min, max) for the slider
        breakeven_price    — default break-even electricity price
        breakeven_range    — (min, max) for the number input
        efficiency_kwh_per_kg — energy needed per kg of H₂
        water_cost_per_kg  — water cost per kg of H₂
        min_run_hours      — minimum continuous run time
    """
    return {
        "capacity_mw": 10,
        "capacity_range": (1, 50),
        "breakeven_price": 45.0,
        "breakeven_range": (10.0, 120.0),
        "efficiency_kwh_per_kg": 55,
        "water_cost_per_kg": 0.05,
        "min_run_hours": 2,
    }


# =====================================================================
# OPTIMISED SCHEDULE
# =====================================================================

def get_optimised_schedule(
    region_abbr: str = "NSW",
    breakeven: float = 45.0,
    capacity_mw: float = 10.0,
    horizon_hours: int = 168,
) -> pd.DataFrame:
    """
    Build a production schedule using real historical prices + ML forecast.

    For each hour, the optimizer checks:
        price < breakeven?  → produce = True  (make hydrogen)
        price >= breakeven? → produce = False (hold, too expensive)

    The schedule combines:
      - Recent real AEMO prices (last 7 days of actuals)
      - ML-forecasted prices (for hours beyond the latest data)

    Parameters:
        region_abbr:   NEM region, e.g. "NSW", "VIC", "QLD", "SA", "TAS"
        breakeven:     break-even electricity price (AUD/MWh)
        capacity_mw:   electrolyser capacity in megawatts
        horizon_hours: how many hours the schedule covers (default 168 = 7 days)

    Returns DataFrame with columns:
        timestamp      (datetime)
        price_aud_mwh  (float — real or forecasted)
        source         (str — "historical" or "forecast")
        produce        (bool — True if price < breakeven)
        h2_kg          (float — hydrogen produced this hour)
        cost_aud       (float — electricity cost this hour)
    """

    # ── Load real historical prices ──
    hist_df = load_prices(region_abbr)

    # Take the most recent hours from the historical data
    # (up to horizon_hours, but usually we have more than enough)
    recent = hist_df.tail(horizon_hours).copy()
    recent["source"] = "historical"

    # ── If we need more hours than history provides, use ML forecast ──
    forecast_hours_needed = horizon_hours - len(recent)

    if forecast_hours_needed > 0:
        # Run the ML forecast to get predicted future prices
        fc = run_forecast(region_abbr=region_abbr, horizon_hours=forecast_hours_needed)

        # Extract only the forecast portion (not the historical overlay)
        fc_start = fc["hist_hours"]
        fc_timestamps = fc["timestamps"][fc_start:]
        fc_prices = fc["predicted"][fc_start:]

        forecast_df = pd.DataFrame({
            "timestamp": fc_timestamps,
            "price_aud_mwh": fc_prices,
            "source": "forecast",
        })

        # Combine historical + forecast
        schedule = pd.concat([recent[["timestamp", "price_aud_mwh", "source"]],
                              forecast_df], ignore_index=True)
    else:
        schedule = recent[["timestamp", "price_aud_mwh", "source"]].copy()

    # Trim to exactly horizon_hours
    schedule = schedule.tail(horizon_hours).reset_index(drop=True)

    # ── Apply the optimizer logic ──
    # This is the core decision: produce if price is below break-even
    schedule["produce"] = schedule["price_aud_mwh"] < breakeven

    # Calculate hydrogen output per hour:
    #   capacity (MW) × 1 hour × 1000 (kW/MW) / 55 (kWh per kg H₂)
    kg_per_hour = capacity_mw * 1000 / 55
    schedule["h2_kg"] = np.where(schedule["produce"], round(kg_per_hour, 1), 0)

    # Calculate electricity cost per hour:
    #   price (AUD/MWh) × capacity (MW) × 1 hour
    schedule["cost_aud"] = np.where(
        schedule["produce"],
        np.round(schedule["price_aud_mwh"] * capacity_mw, 2),
        0,
    )

    return schedule


# =====================================================================
# OPTIMIZER SUMMARY (Optimised vs Naive comparison)
# =====================================================================

def get_optimizer_summary(
    region_abbr: str = "NSW",
    breakeven: float = 45.0,
    capacity_mw: float = 10.0,
) -> dict:
    """
    Compare optimised scheduling vs naive 24/7 production.

    Returns a dict with three sections:
        "optimised" — metrics for the smart schedule
        "naive"     — metrics for running non-stop
        "savings"   — how much the optimizer saves

    Each section includes:
        total_cost_aud, total_h2_kg, production_hours,
        avg_elec_price, cost_per_kg
    """
    # Get the optimised schedule
    schedule = get_optimised_schedule(region_abbr, breakeven, capacity_mw)
    total_hours = len(schedule)
    prod_hours = int(schedule["produce"].sum())

    # ── Optimised metrics ──
    optimised_cost = float(schedule["cost_aud"].sum())
    optimised_h2 = float(schedule["h2_kg"].sum())
    avg_price_during_prod = float(
        schedule.loc[schedule["produce"], "price_aud_mwh"].mean()
    ) if prod_hours > 0 else 0

    # ── Naive metrics (run 24/7 regardless of price) ──
    kg_per_hour = capacity_mw * 1000 / 55
    naive_cost = float((schedule["price_aud_mwh"] * capacity_mw).sum())
    naive_h2 = round(kg_per_hour * total_hours, 1)

    # ── Savings ──
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
