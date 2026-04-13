"""
3days_Prices_WA_NEM.py — Fetch 7-day electricity prices from OpenElectricity API.

Renamed from '3days_Prices_WA&NEM.py' — the '&' was replaced with '_' because
Python cannot import filenames containing '&'.

When run directly:   python 3days_Prices_WA_NEM.py
    → fetches data and writes to '7 days elec price.csv' in this directory

When imported:        from data.electricity_prices.3days_Prices_WA_NEM import retrieve_all_data
    → NOTE: because the filename starts with a digit, a normal import won't work.
      The electricity_prices_loader.py uses importlib to handle this.
      Call retrieve_all_data() to refresh the CSV programmatically.
"""

from datetime import datetime, timezone, timedelta
import requests
from zoneinfo import ZoneInfo
import csv
import os
import json


# ============================================================
# API CONFIG
# ============================================================

API_KEY = "oe_DYiKF1FeoE9VzmEPNuzUCV"
BASE_URL = "https://api.openelectricity.org.au/v4/market/network"

REGION_TIMEZONES = {
    "AU-SA":  "Australia/Adelaide",
    "AU-VIC": "Australia/Melbourne",
    "AU-NSW": "Australia/Sydney",
    "AU-QLD": "Australia/Brisbane",
    "AU-TAS": "Australia/Hobart",
    "AU-WA":  "Australia/Perth",
}

# NEM sub-regions map to AU codes
NETWORK_REGION_TO_AU = {
    "SA1":  "AU-SA",
    "VIC1": "AU-VIC",
    "NSW1": "AU-NSW",
    "QLD1": "AU-QLD",
    "TAS1": "AU-TAS",
}

# Use absolute path so it works both when run directly AND when imported
# by the Streamlit app (which runs from a different working directory)
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE = os.path.join(_THIS_DIR, "7 days elec price.csv")
RAW_DEBUG_NEM = os.path.join(_THIS_DIR, "last_nem_response.json")
RAW_DEBUG_WEM = os.path.join(_THIS_DIR, "last_wem_response.json")

# ============================================================
# CSV
# ============================================================

def init_csv():
    """Create the CSV file with headers (overwrites any existing file
    so we get a clean 7-day window each time)."""
    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["region_code", "date", "price"])

def append_to_csv(region, region_dt, price):
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            region,
            region_dt.strftime("%Y-%m-%d %H:%M:%S"),
            price
        ])

# ============================================================
# HELPERS
# ============================================================

def parse_dt(value):
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value).astimezone(timezone.utc)
    except Exception:
        return None

def process_and_save(region, data_pairs):
    """Save ALL data points (every 5 min) for the given region."""
    tz = ZoneInfo(REGION_TIMEZONES[region])
    saved = 0

    for ts_str, price in data_pairs:
        if price is None:
            continue
        api_dt = parse_dt(ts_str)
        if api_dt is None:
            continue
        region_dt = api_dt.astimezone(tz)

        append_to_csv(region, region_dt, price)
        saved += 1

    if saved == 0:
        print(f"✗ {region} | No valid data points found")
        return False

    print(f"✓ {region} | {saved} data points saved")
    return True

# ============================================================
# 7-day time window
# ============================================================

def get_7day_window():
    """Return start and end as ISO-8601 strings (UTC)."""
    now_utc = datetime.now(timezone.utc)
    start_utc = now_utc - timedelta(days=7)
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    return start_utc.strftime(fmt), now_utc.strftime(fmt)

# ============================================================
# NEM
# ============================================================

def retrieve_nem_data():
    start, end = get_7day_window()
    headers = {"Authorization": f"Bearer {API_KEY}"}
    response = requests.get(
        f"{BASE_URL}/NEM",
        headers=headers,
        params={
            "interval": "5m",
            "metrics": "price",
            "primary_grouping": "network_region",
            "with_clerk": "true",
            "start": start,
            "end":   end,
        },
        timeout=30
    )

    if response.status_code != 200:
        print(f"✗ NEM Error: {response.status_code} | {response.text}")
        return

    api_response = response.json()
    with open(RAW_DEBUG_NEM, "w", encoding="utf-8") as f:
        json.dump(api_response, f, indent=2, ensure_ascii=False)

    data = api_response.get("data", [])
    if not isinstance(data, list) or not data:
        print("✗ NEM: No data in response")
        return

    wrote_anything = False
    for top_item in data:
        for result in top_item.get("results", []):
            columns = result.get("columns", {})
            raw_region = columns.get("region")
            region = NETWORK_REGION_TO_AU.get(raw_region)
            if region not in REGION_TIMEZONES:
                continue
            data_pairs = result.get("data", [])
            if not isinstance(data_pairs, list) or not data_pairs:
                continue
            if process_and_save(region, data_pairs):
                wrote_anything = True

    if not wrote_anything:
        print(f"✗ NEM: No parseable records. Check {RAW_DEBUG_NEM}")

# ============================================================
# WEM (Western Australia)
# ============================================================

def retrieve_wem_data():
    start, end = get_7day_window()
    headers = {"Authorization": f"Bearer {API_KEY}"}
    response = requests.get(
        f"{BASE_URL}/WEM",
        headers=headers,
        params={
            "interval": "5m",
            "metrics": "price",
            "start": start,
            "end":   end,
        },
        timeout=30
    )

    if response.status_code != 200:
        print(f"✗ WEM Error: {response.status_code} | {response.text}")
        return

    api_response = response.json()
    with open(RAW_DEBUG_WEM, "w", encoding="utf-8") as f:
        json.dump(api_response, f, indent=2, ensure_ascii=False)

    data = api_response.get("data", [])
    if not isinstance(data, list) or not data:
        print("✗ WEM: No data in response")
        return

    wrote_anything = False
    for top_item in data:
        for result in top_item.get("results", []):
            data_pairs = result.get("data", [])
            if not isinstance(data_pairs, list) or not data_pairs:
                continue
            if process_and_save("AU-WA", data_pairs):
                wrote_anything = True

    if not wrote_anything:
        print(f"✗ WEM: No parseable records. Check {RAW_DEBUG_WEM}")

# ============================================================
# COMBINED — call this from other modules
# ============================================================

def retrieve_all_data():
    """Fetch 7 days of NEM + WEM prices and write to CSV.
    Safe to call from the Streamlit app or from the command line."""
    init_csv()
    print("▶ Fetching all data for the last 7 days (NEM + WEM)...")
    retrieve_nem_data()
    retrieve_wem_data()
    print("▶ Done! All data saved to:", CSV_FILE)

# ============================================================
# Only run automatically when executed directly as a script.
# When imported by the Streamlit app, nothing runs until
# retrieve_all_data() is explicitly called.
# ============================================================

if __name__ == "__main__":
    retrieve_all_data()
