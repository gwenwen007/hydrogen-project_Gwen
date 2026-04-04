import schedule
import time
from datetime import datetime, timezone
import requests
import pytz
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

CSV_FILE = "electricity_price_data.csv"
RAW_DEBUG_NEM = "last_nem_response.json"
RAW_DEBUG_WEM = "last_wem_response.json"

# ============================================================
# DATA STORAGE
# ============================================================

class ElectricityPriceAU:
    def __init__(self):
        self.storage = {}

au_price = ElectricityPriceAU()

# ============================================================
# CSV
# ============================================================

def init_csv():
    if not os.path.exists(CSV_FILE):
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

def get_latest_non_null(data_pairs):
    for ts_str, price in reversed(data_pairs):
        if price is not None:
            return ts_str, price
    return None, None

def process_and_save(region, data_pairs):
    ts_str, price = get_latest_non_null(data_pairs)
    if ts_str is None or price is None:
        print(f"✗ {region} | No valid price found")
        return False

    api_dt = parse_dt(ts_str)
    if api_dt is None:
        print(f"✗ {region} | Invalid timestamp: {ts_str}")
        return False

    tz = pytz.timezone(REGION_TIMEZONES[region])
    region_dt = api_dt.astimezone(tz)

    if region not in au_price.storage:
        au_price.storage[region] = {}
    au_price.storage[region][region_dt] = price
    append_to_csv(region, region_dt, price)

    print(f"✓ {region} | {region_dt.strftime('%d.%m.%Y %H:%M')} → {price} $/MWh")
    return True

# ============================================================
# NEM 
# ============================================================

def retrieve_nem_data():
    headers = {"Authorization": f"Bearer {API_KEY}"}
    response = requests.get(
        f"{BASE_URL}/NEM",
        headers=headers,
        params={
            "interval": "5m",
            "metrics": "price",
            "primary_grouping": "network_region",
            "with_clerk": "true"
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
# NEUE CODE FèR WEM (Western Australia) --> Abgegrenzt vom NEM, aufgrund der untershciedlichen API Endpunkte...
# ============================================================

def retrieve_wem_data():
    headers = {"Authorization": f"Bearer {API_KEY}"}
    response = requests.get(
        f"{BASE_URL}/WEM",
        headers=headers,
        params={
            "interval": "5m",
            "metrics": "price",
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
# COMBINED
# ============================================================

def retrieve_all_data():
    retrieve_nem_data()
    retrieve_wem_data()

# ============================================================
# START
# ============================================================

init_csv()

print("▶ Fetching current data (NEM + WEM):")
retrieve_all_data()

schedule.every(5).minutes.do(retrieve_all_data)

print("▶ Scheduler started: data updates every 5 minutes")

while True:
    schedule.run_pending()
    time.sleep(30)