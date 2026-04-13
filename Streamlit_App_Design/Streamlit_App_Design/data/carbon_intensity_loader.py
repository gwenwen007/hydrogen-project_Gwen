"""
carbon_intensity_loader.py — Load carbon intensity data from two sources.

This module merges data from:
  1. Historical CSV files (data/carbon_intensity/carbon_*.csv)
     — Bulk data collected earlier, covering Oct 2025 – Apr 2026
  2. Live 7-day API (data/carbon_intensity/carbon_intensity_API_past7d)
     — Real-time data from the Electricity Maps API, last ~7 days

The live data supplements the CSVs so that the app always has the
most recent carbon intensity readings.  If the API call fails or
the module is unavailable, we gracefully fall back to CSV data only.

Usage:
    from data.carbon_intensity_loader import get_carbon_intensity

    df = get_carbon_intensity(region_abbr="NSW", days=30)
    # → DataFrame with columns: datetime, carbon_intensity
"""

import os
import pandas as pd


# =====================================================================
# REGION MAPPING
# =====================================================================
# Map short region abbreviations (used in the sidebar) to the
# Electricity Maps API region codes (used in the CSV filenames).

_CARBON_REGION_MAP = {
    "NSW": "AU-NSW",
    "VIC": "AU-VIC",
    "QLD": "AU-QLD",
    "SA":  "AU-SA",
    "TAS": "AU-TAS",
}

# Map API region codes to the actual CSV file paths.
# Each file contains hourly carbon intensity data for one region.
_CARBON_DIR = os.path.join(os.path.dirname(__file__), "carbon_intensity")

_CARBON_CSV_FILES = {
    "AU-NSW": os.path.join(_CARBON_DIR, "carbon_nsw.csv"),
    "AU-VIC": os.path.join(_CARBON_DIR, "carbon_vic.csv"),
    "AU-QLD": os.path.join(_CARBON_DIR, "carbon_qld.csv"),
    "AU-SA":  os.path.join(_CARBON_DIR, "carbon_sa.csv"),
    "AU-TAS": os.path.join(_CARBON_DIR, "carbon_tas.csv"),
}


# =====================================================================
# LIVE 7-DAY API LOADER
# =====================================================================

def _load_live_carbon(region_abbr: str) -> pd.DataFrame:
    """
    Fetch the last 7 days of carbon intensity from the live API.

    Uses the fetch_carbon_intensity_7d() function from the renamed
    module data/carbon_intensity/carbon_intensity_api_past7d.py.

    Returns DataFrame with columns: datetime, carbon_intensity
    Returns empty DataFrame if the API fails or module is unavailable.
    """
    try:
        # Clean import — file was renamed to have a proper .py extension
        # and a Python-compatible filename (no spaces, no special chars)
        from data.carbon_intensity.carbon_intensity_api_past7d import fetch_carbon_intensity_7d

        # Call the API function
        result = fetch_carbon_intensity_7d(region_abbr)

        # Check for errors
        if "error" in result:
            return pd.DataFrame(columns=["datetime", "carbon_intensity"])

        # Convert the list of dicts to a DataFrame
        records = result.get("data", [])
        if not records:
            return pd.DataFrame(columns=["datetime", "carbon_intensity"])

        df = pd.DataFrame(records)
        df["datetime"] = pd.to_datetime(df["datetime"])
        df["carbon_intensity"] = pd.to_numeric(
            df["carbon_intensity"], errors="coerce"
        )
        df = df.dropna(subset=["carbon_intensity"])

        return df[["datetime", "carbon_intensity"]]

    except Exception:
        # If anything goes wrong (module not found, API key invalid,
        # network error, etc.), fall back silently to CSV data
        return pd.DataFrame(columns=["datetime", "carbon_intensity"])


# =====================================================================
# MAIN LOADER FUNCTION
# =====================================================================

def get_carbon_intensity(region_abbr: str = "NSW", days: int = 30) -> pd.DataFrame:
    """
    Load carbon intensity data for a given NEM region.

    Combines historical CSV data with live 7-day API data.  The live
    data takes priority for any overlapping hours (it's more recent).

    Parameters:
        region_abbr: short region name, e.g. "NSW", "VIC", "QLD", "SA", "TAS"
        days:        how many days of history to return (default 30)

    Returns DataFrame with columns:
        datetime          (pd.Timestamp)  — hourly timestamp
        carbon_intensity  (float)         — gCO₂eq/kWh
    """
    # ── Load historical CSV data ──
    region_code = _CARBON_REGION_MAP.get(region_abbr, "AU-NSW")
    csv_path = _CARBON_CSV_FILES.get(region_code)

    try:
        hist = pd.read_csv(csv_path)
        hist["datetime"] = pd.to_datetime(hist["datetime"])
        hist = hist.sort_values("datetime")
    except Exception:
        hist = pd.DataFrame(columns=["datetime", "carbon_intensity"])

    # ── Load live 7-day API data ──
    live = _load_live_carbon(region_abbr)

    # ── Merge: live data overwrites overlapping historical hours ──
    if not live.empty and not hist.empty:
        # Remove historical rows that overlap with live data
        hist = hist[~hist["datetime"].isin(live["datetime"])]
        combined = pd.concat([hist, live], ignore_index=True)
    elif not live.empty:
        combined = live
    else:
        combined = hist

    # Sort and filter to requested time range
    combined = combined.sort_values("datetime")

    if len(combined) > 0:
        cutoff = combined["datetime"].max() - pd.Timedelta(days=days)
        combined = combined[combined["datetime"] >= cutoff]

    return combined.reset_index(drop=True)
