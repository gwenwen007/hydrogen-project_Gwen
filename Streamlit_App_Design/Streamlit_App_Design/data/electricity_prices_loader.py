"""
electricity_prices_loader.py — Loads real AEMO electricity price data.

This module reads TWO data sources and merges them:

  1. Historical AEMO CSVs (PRICE_AND_DEMAND_YYYYMM_REGION.csv)
     - Monthly 5-minute interval data downloaded in bulk
     - Columns: REGION, SETTLEMENTDATE, TOTALDEMAND, RRP, PERIODTYPE

  2. Live 7-day API data ("7 days elec price.csv")
     - Produced by 3days_Prices_WA&NEM.py via the OpenElectricity API
     - Columns: region_code, date, price
     - Refreshed on demand; covers the most recent ~7 days

The live data supplements the historical CSVs so that the app always
has near-real-time prices.  If the live CSV doesn't exist yet (API
not run), the loader gracefully falls back to historical data only.

We aggregate everything to hourly averages because:
  - 5-minute data is too noisy for visualisation
  - Our ML model predicts hourly prices
  - Charts load faster with ~8,700 rows/year vs ~105,000

Usage in any page:
    from data.electricity_prices_loader import load_prices

Data files:
    data/electricity_prices/PRICE_AND_DEMAND_YYYYMM_REGION.csv  (historical)
    data/electricity_prices/7 days elec price.csv                (live API)
"""

import os
import glob
import pandas as pd
import streamlit as st


# Directory where the AEMO CSV files are stored
_PRICES_DIR = os.path.join(os.path.dirname(__file__), "electricity_prices")

# Map our short region names to the AEMO region codes used in filenames
_REGION_FILE_CODES = {
    "NSW": "NSW1",
    "VIC": "VIC1",
    "QLD": "QLD1",
    "SA":  "SA1",
    "TAS": "TAS1",
}

# Map the live API region codes (e.g. "AU-NSW") back to our short names.
# The 3d price API uses the Electricity Maps convention for region codes.
_LIVE_API_REGION_MAP = {
    "AU-NSW": "NSW",
    "AU-VIC": "VIC",
    "AU-QLD": "QLD",
    "AU-SA":  "SA",
    "AU-TAS": "TAS",
    "AU-WA":  "WA",
}

# Path to the live 7-day price CSV produced by the API script
_LIVE_CSV_PATH = os.path.join(_PRICES_DIR, "7 days elec price.csv")


def _load_live_prices(region_abbr: str) -> pd.DataFrame:
    """
    Load live 7-day prices from the API CSV for one region.

    The API script (3days_Prices_WA&NEM.py) writes a single CSV with
    all regions combined.  We filter to the requested region and
    aggregate from 5-minute to hourly averages.

    Parameters:
        region_abbr: short region name, e.g. "NSW", "VIC"

    Returns DataFrame with columns:
        timestamp      (datetime, hourly)
        price_aud_mwh  (float, hourly average)
    Returns empty DataFrame if the CSV doesn't exist or has no data.
    """
    if not os.path.exists(_LIVE_CSV_PATH):
        return pd.DataFrame(columns=["timestamp", "price_aud_mwh"])

    try:
        live = pd.read_csv(_LIVE_CSV_PATH)
    except Exception:
        return pd.DataFrame(columns=["timestamp", "price_aud_mwh"])

    # The CSV has columns: region_code, date, price
    # region_code uses the API format (e.g. "AU-NSW")
    if "region_code" not in live.columns or "date" not in live.columns:
        return pd.DataFrame(columns=["timestamp", "price_aud_mwh"])

    # Map the API region code back to our short abbreviation
    live["region_short"] = live["region_code"].map(_LIVE_API_REGION_MAP)

    # Filter to the requested region
    region_data = live[live["region_short"] == region_abbr].copy()
    if region_data.empty:
        return pd.DataFrame(columns=["timestamp", "price_aud_mwh"])

    # Parse timestamps and aggregate to hourly
    region_data["timestamp"] = pd.to_datetime(region_data["date"])
    region_data["hour"] = region_data["timestamp"].dt.floor("h")
    region_data["price"] = pd.to_numeric(region_data["price"], errors="coerce")

    hourly = region_data.groupby("hour").agg(
        price_aud_mwh=("price", "mean"),
    ).reset_index()
    hourly.rename(columns={"hour": "timestamp"}, inplace=True)
    hourly["price_aud_mwh"] = hourly["price_aud_mwh"].round(2)

    return hourly


@st.cache_data(ttl=3600, show_spinner="Refreshing live prices from AEMO API...")
def _refresh_live_prices_from_api():
    """
    Call the OpenElectricity API to fetch 7 days of price data and
    write it to the CSV.  Cached for 1 hour (ttl=3600) so we don't
    hit the API on every page load or interaction.

    This replaces the old workflow where 3days_Prices_WA&NEM.py had
    to be run manually as a separate script.

    We use importlib because the filename starts with a digit ('3days_...')
    which makes a normal 'from ... import' statement impossible in Python.
    """
    try:
        import importlib.util
        module_path = os.path.join(_PRICES_DIR, "3days_Prices_WA_NEM.py")
        spec = importlib.util.spec_from_file_location("prices_api", module_path)
        api_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(api_module)
        api_module.retrieve_all_data()
        return True
    except Exception as e:
        print(f"⚠ Live price refresh failed: {e}")
        return False


def load_prices(region_abbr: str = "NSW") -> pd.DataFrame:
    """
    Load and concatenate all AEMO price CSVs for a given NEM region,
    then aggregate from 5-minute intervals to hourly averages.

    If a live 7-day API CSV exists, its data is merged in so that the
    most recent hours are always available.  Live data overwrites any
    overlapping historical hours (live is fresher).

    Automatically refreshes the live CSV via the API (cached for 1 hour).

    Parameters:
        region_abbr: short region name, e.g. "NSW", "VIC", "QLD", "SA", "TAS"

    Returns DataFrame with columns:
        timestamp       (datetime, hourly)
        price_aud_mwh   (float, hourly average RRP in AUD/MWh)
        demand_gw       (float, hourly average total demand in GW)
    """
    # Automatically refresh the live 7-day CSV from the API.
    # This is cached for 1 hour so repeated page loads don't re-fetch.
    _refresh_live_prices_from_api()

    # Get the AEMO file code for this region (e.g. "NSW" → "NSW1")
    file_code = _REGION_FILE_CODES.get(region_abbr, "NSW1")

    # Find all CSV files matching this region using a glob pattern
    # e.g. PRICE_AND_DEMAND_202501_NSW1.csv, PRICE_AND_DEMAND_202502_NSW1.csv, ...
    pattern = os.path.join(_PRICES_DIR, f"PRICE_AND_DEMAND_*_{file_code}.csv")
    csv_files = sorted(glob.glob(pattern))

    # ── Load historical AEMO data ──
    if csv_files:
        # Read and concatenate all monthly CSVs into one big DataFrame
        frames = []
        for f in csv_files:
            df = pd.read_csv(f)
            frames.append(df)
        raw = pd.concat(frames, ignore_index=True)

        # Parse the settlement date column into proper datetime objects
        raw["timestamp"] = pd.to_datetime(raw["SETTLEMENTDATE"])

        # Floor each timestamp to the hour (e.g. 14:35 → 14:00)
        # This groups all 5-minute intervals within each hour together
        raw["hour"] = raw["timestamp"].dt.floor("h")

        # Aggregate: average price and demand per hour
        hourly = raw.groupby("hour").agg(
            price_aud_mwh=("RRP", "mean"),             # average price
            demand_mw=("TOTALDEMAND", "mean"),          # average demand in MW
        ).reset_index()

        # Rename the hour column to timestamp for consistency
        hourly.rename(columns={"hour": "timestamp"}, inplace=True)

        # Convert demand from MW to GW (divide by 1000) for cleaner display
        hourly["demand_gw"] = (hourly["demand_mw"] / 1000).round(2)
        hourly.drop(columns=["demand_mw"], inplace=True)

        # Round price to 2 decimal places
        hourly["price_aud_mwh"] = hourly["price_aud_mwh"].round(2)
    else:
        hourly = pd.DataFrame(columns=["timestamp", "price_aud_mwh", "demand_gw"])

    # ── Load live 7-day API data (if available) ──
    # The live CSV is produced by 3days_Prices_WA&NEM.py and contains
    # the most recent ~7 days of 5-minute data from the OpenElectricity API.
    live = _load_live_prices(region_abbr)

    if not live.empty:
        # The live data doesn't include demand, so set it to NaN
        live["demand_gw"] = float("nan")

        # Merge: live data takes priority for overlapping hours.
        # We remove any historical rows whose timestamp also appears
        # in the live data, then append the live rows.
        if not hourly.empty:
            hourly = hourly[~hourly["timestamp"].isin(live["timestamp"])]

        hourly = pd.concat([hourly, live], ignore_index=True)

    # Sort chronologically
    hourly = hourly.sort_values("timestamp").reset_index(drop=True)

    return hourly
