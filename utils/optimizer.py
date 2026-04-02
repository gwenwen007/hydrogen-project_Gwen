"""
Optimizer Module — Production Scheduling
==========================================
Takes predicted prices + user parameters and determines the cheapest hours
to run the electrolyzer.

The logic is straightforward:
1. Calculate how many hours of production are needed to hit the target volume.
2. Sort forecast hours by price (ascending).
3. Pick the cheapest hours up to the required production time.
4. Calculate total cost and compare to an "average price" baseline.

Other files use this module like so:
    from utils.optimizer import optimize_schedule, calculate_savings
"""

import pandas as pd
import numpy as np


def optimize_schedule(
    price_forecast: pd.DataFrame,
    electrolyzer_capacity_mw: float,
    efficiency_kwh_per_kg: float,
    target_h2_kg: float,
) -> pd.DataFrame:
    """
    Select the cheapest hours to produce a target amount of hydrogen.

    Parameters
    ----------
    price_forecast : pd.DataFrame
        Must have columns ["timestamp", "predicted_price_aud_mwh"].
    electrolyzer_capacity_mw : float
        Electrolyzer nameplate capacity in MW.
    efficiency_kwh_per_kg : float
        Energy required to produce 1 kg of H2 (typically 50–55 kWh/kg).
    target_h2_kg : float
        Desired hydrogen output in kg.

    Returns
    -------
    pd.DataFrame
        The input DataFrame with added columns:
        - "produce" (bool)      — True if this hour is selected for production
        - "h2_produced_kg"      — kg of H2 produced in this hour (0 if not selected)
        - "electricity_cost_aud"— cost of electricity in this hour
    """
    df = price_forecast.copy()

    # How much H2 can the electrolyzer produce per hour?
    # capacity (MW) * 1000 = kW, divided by energy per kg = kg/hour
    kg_per_hour = (electrolyzer_capacity_mw * 1000) / efficiency_kwh_per_kg

    # How many full hours of production do we need?
    hours_needed = int(np.ceil(target_h2_kg / kg_per_hour))
    hours_needed = min(hours_needed, len(df))  # can't exceed forecast horizon

    # Sort by price, pick the cheapest hours
    df = df.sort_values("predicted_price_aud_mwh").reset_index(drop=True)
    df["produce"] = False
    df.loc[:hours_needed - 1, "produce"] = True

    # Calculate production and cost for selected hours
    df["h2_produced_kg"] = np.where(df["produce"], kg_per_hour, 0)
    # Cost = price (AUD/MWh) * capacity (MW) * 1 hour
    df["electricity_cost_aud"] = np.where(
        df["produce"],
        df["predicted_price_aud_mwh"] * electrolyzer_capacity_mw,
        0,
    )

    # Re-sort by timestamp for display
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def calculate_savings(schedule: pd.DataFrame, electrolyzer_capacity_mw: float) -> dict:
    """
    Compare optimized cost against a naive 'always-on' baseline.

    Parameters
    ----------
    schedule : pd.DataFrame
        Output of optimize_schedule().
    electrolyzer_capacity_mw : float
        Electrolyzer capacity in MW.

    Returns
    -------
    dict with keys:
        - "optimized_cost_aud"   : total cost using optimized hours
        - "baseline_cost_aud"    : cost if running during the same number of
                                   hours but at the average price
        - "savings_aud"          : absolute savings
        - "savings_pct"          : percentage savings
        - "avg_price_optimized"  : average price during selected hours
        - "avg_price_all"        : average price across the whole forecast
        - "total_h2_kg"          : total hydrogen produced
    """
    production_hours = schedule[schedule["produce"]]
    n_hours = len(production_hours)

    optimized_cost = production_hours["electricity_cost_aud"].sum()
    avg_price_all = schedule["predicted_price_aud_mwh"].mean()
    baseline_cost = avg_price_all * electrolyzer_capacity_mw * n_hours

    savings = baseline_cost - optimized_cost
    savings_pct = (savings / baseline_cost * 100) if baseline_cost != 0 else 0

    return {
        "optimized_cost_aud": round(optimized_cost, 2),
        "baseline_cost_aud": round(baseline_cost, 2),
        "savings_aud": round(savings, 2),
        "savings_pct": round(savings_pct, 1),
        "avg_price_optimized": round(production_hours["predicted_price_aud_mwh"].mean(), 2),
        "avg_price_all": round(avg_price_all, 2),
        "total_h2_kg": round(production_hours["h2_produced_kg"].sum(), 1),
    }
