"""
cost_analysis_model.py — Cost analysis functions using real optimizer output.

This module replaces the hardcoded sample data with calculations based
on the actual production optimizer results (which in turn use real
AEMO prices + ML-forecasted prices).

The key insight: electricity cost comes from get_optimizer_summary(),
and non-electricity costs (water, maintenance, labour, depreciation)
are user-editable defaults stored in session state.

Usage:
    from data.cost_analysis_model import (
        get_default_cost_items,
        get_cost_breakdown,
        get_sensitivity_analysis,
        get_export_data,
        get_historical_cost_trend,
    )
"""

import numpy as np
import pandas as pd

# Real data sources — we pull electricity cost from the optimizer
from data.production_optimizer_model import (
    get_optimised_schedule,
    get_optimizer_summary,
)
from data.electricity_prices_loader import load_prices


# =====================================================================
# DEFAULT NON-ELECTRICITY COST ITEMS
# =====================================================================
# These are sensible defaults for a 10 MW electrolyser over a 7-day
# production window.  The user can edit these in the UI.

def get_default_cost_items() -> list[dict]:
    """
    Return a list of default non-electricity cost items.

    Each item is a dict with:
        name     — cost category label
        cost_aud — cost in AUD for the production window

    These defaults assume a ~7-day production period.  The user can
    override each value via number inputs in the Cost Analysis modal.
    """
    return [
        {"name": "Water",          "cost_aud": 420.00},
        {"name": "Maintenance",    "cost_aud": 1250.00},
        {"name": "Labour",         "cost_aud": 2800.00},
        {"name": "Depreciation",   "cost_aud": 3500.00},
    ]


# =====================================================================
# COST BREAKDOWN (for the donut chart)
# =====================================================================

def get_cost_breakdown(
    region_abbr: str = "NSW",
    breakeven: float = 45.0,
    capacity_mw: float = 10.0,
    extra_costs: list[dict] | None = None,
) -> pd.DataFrame:
    """
    Build the cost breakdown DataFrame using real optimizer electricity cost.

    Parameters:
        region_abbr:  NEM region abbreviation (e.g. "NSW", "VIC")
        breakeven:    break-even price in AUD/MWh (from sidebar/slider)
        capacity_mw:  electrolyser capacity in MW
        extra_costs:  list of dicts with {"name": str, "cost_aud": float}
                      representing non-electricity costs.  If None, uses
                      get_default_cost_items().

    Returns DataFrame with columns:
        category  (str)   — cost category name
        cost_aud  (float) — cost in AUD
    """
    # ── Get real electricity cost from the optimizer ──
    # The optimizer summary compares optimised vs naive production
    # and gives us the total electricity cost for the optimised schedule.
    summary = get_optimizer_summary(region_abbr, breakeven, capacity_mw)
    electricity_cost = summary["optimised"]["total_cost_aud"]

    # ── Build the cost items list ──
    # Start with electricity (always first — it's the dominant cost)
    if extra_costs is None:
        extra_costs = get_default_cost_items()

    # Only include items with cost > 0 (setting to 0 removes them)
    active_extras = [item for item in extra_costs if item["cost_aud"] > 0]

    categories = ["Electricity"] + [item["name"] for item in active_extras]
    costs = [round(electricity_cost, 2)] + [item["cost_aud"] for item in active_extras]

    return pd.DataFrame({
        "category": categories,
        "cost_aud": costs,
    })


# =====================================================================
# SENSITIVITY ANALYSIS
# =====================================================================

def get_sensitivity_analysis(
    region_abbr: str = "NSW",
    breakeven: float = 45.0,
    capacity_mw: float = 10.0,
    extra_costs: list[dict] | None = None,
) -> pd.DataFrame:
    """
    Compute how H₂ cost per kg changes when electricity prices shift.

    We run 7 scenarios from -20% to +20% change in electricity price.
    For each scenario, we recalculate:
        new_elec_cost = base_elec_cost × (1 + pct/100)
        total_cost = new_elec_cost + sum(non_electricity_costs)
        cost_per_kg = total_cost / total_h2_kg

    Parameters:
        region_abbr:  NEM region
        breakeven:    break-even price AUD/MWh
        capacity_mw:  electrolyser capacity MW
        extra_costs:  user-edited non-electricity cost items

    Returns DataFrame with columns:
        price_change_pct  (int)   — scenario (e.g. -20, 0, +20)
        h2_cost_per_kg    (float) — resulting cost per kg
        change_vs_base    (float) — difference from base case
    """
    # ── Get real optimizer numbers ──
    summary = get_optimizer_summary(region_abbr, breakeven, capacity_mw)
    base_elec_cost = summary["optimised"]["total_cost_aud"]
    total_h2_kg = summary["optimised"]["total_h2_kg"]

    # ── Sum non-electricity costs ──
    if extra_costs is None:
        extra_costs = get_default_cost_items()
    non_elec_total = sum(item["cost_aud"] for item in extra_costs)

    # ── Base cost per kg ──
    if total_h2_kg > 0:
        base_cost_per_kg = (base_elec_cost + non_elec_total) / total_h2_kg
    else:
        base_cost_per_kg = 0

    # ── Run scenarios ──
    scenarios = [-20, -10, -5, 0, 5, 10, 20]
    rows = []
    for pct in scenarios:
        # Scale electricity cost by the scenario percentage
        new_elec_cost = base_elec_cost * (1 + pct / 100)
        new_total = new_elec_cost + non_elec_total

        # Cost per kg under this scenario
        if total_h2_kg > 0:
            new_cost_per_kg = new_total / total_h2_kg
        else:
            new_cost_per_kg = 0

        rows.append({
            "price_change_pct": pct,
            "h2_cost_per_kg": round(new_cost_per_kg, 2),
            "change_vs_base": round(new_cost_per_kg - base_cost_per_kg, 2),
        })

    return pd.DataFrame(rows)


# =====================================================================
# HISTORICAL COST TREND
# =====================================================================

def get_historical_cost_trend(
    region_abbr: str = "NSW",
    capacity_mw: float = 10.0,
    extra_costs: list[dict] | None = None,
) -> pd.DataFrame:
    """
    Compute monthly average H₂ production cost from real AEMO prices.

    Instead of random sample data, we use the actual historical prices
    to calculate what the cost-per-kg would have been each month.

    Method:
        For each month in the dataset:
        1. Get all hourly prices
        2. Assume the electrolyser runs during cheap hours (below median)
        3. Compute electricity cost per kg = avg_price × kWh_per_kg / 1000
        4. Add non-electricity costs (spread monthly)

    Parameters:
        region_abbr:  NEM region
        capacity_mw:  electrolyser capacity MW
        extra_costs:  non-electricity cost items

    Returns DataFrame with columns:
        month           (datetime) — first day of each month
        cost_per_kg_aud (float)    — average H₂ cost that month
        volume_kg       (int)      — estimated monthly production
    """
    # ── Load real historical prices ──
    prices = load_prices(region_abbr)

    # ── Group by month ──
    prices["month"] = prices["timestamp"].dt.to_period("M").dt.to_timestamp()
    monthly = prices.groupby("month").agg(
        avg_price=("price_aud_mwh", "mean"),       # average hourly price
        cheap_price=("price_aud_mwh", "median"),    # median used as threshold
        hours=("price_aud_mwh", "count"),           # hours of data
    ).reset_index()

    # ── Non-electricity costs (annualised then divided by 12) ──
    if extra_costs is None:
        extra_costs = get_default_cost_items()

    # The default costs are for ~7 days.  Scale to monthly:
    #   weekly cost × (30/7) ≈ monthly cost
    weekly_non_elec = sum(item["cost_aud"] for item in extra_costs)
    monthly_non_elec = weekly_non_elec * (30 / 7)

    # ── Calculate cost per kg for each month ──
    # kg per hour = capacity_mw × 1000 / 55 (kWh per kg H₂)
    kg_per_hour = capacity_mw * 1000 / 55

    rows = []
    for _, row in monthly.iterrows():
        # Assume optimised production: run only during below-median hours
        # That's roughly half the hours in the month
        prod_hours = int(row["hours"] * 0.5)
        monthly_h2_kg = kg_per_hour * prod_hours

        # Electricity cost: below-median prices are roughly 70% of mean
        avg_cheap_price = row["avg_price"] * 0.7
        monthly_elec_cost = avg_cheap_price * capacity_mw * prod_hours

        # Total cost per kg
        total_monthly = monthly_elec_cost + monthly_non_elec
        if monthly_h2_kg > 0:
            cost_per_kg = total_monthly / monthly_h2_kg
        else:
            cost_per_kg = 0

        rows.append({
            "month": row["month"],
            "cost_per_kg_aud": round(cost_per_kg, 2),
            "volume_kg": int(monthly_h2_kg),
        })

    return pd.DataFrame(rows)


# =====================================================================
# CSV EXPORT
# =====================================================================

def get_export_data(
    region_abbr: str = "NSW",
    breakeven: float = 45.0,
    capacity_mw: float = 10.0,
) -> pd.DataFrame:
    """
    Build a comprehensive export DataFrame from the real optimizer schedule.

    Combines the optimised production schedule with cumulative totals.

    Parameters:
        region_abbr:  NEM region
        breakeven:    break-even price AUD/MWh
        capacity_mw:  electrolyser capacity MW

    Returns DataFrame with columns:
        timestamp, price_aud_mwh, source, produce, h2_kg, cost_aud,
        cumulative_h2_kg, cumulative_cost_aud
    """
    # ── Get the real optimised schedule ──
    schedule = get_optimised_schedule(region_abbr, breakeven, capacity_mw)

    # ── Build the export table ──
    export = schedule[[
        "timestamp", "price_aud_mwh", "source", "produce", "h2_kg", "cost_aud"
    ]].copy()

    # Add cumulative columns (running totals)
    export["cumulative_h2_kg"] = export["h2_kg"].cumsum().round(1)
    export["cumulative_cost_aud"] = export["cost_aud"].cumsum().round(2)

    return export
