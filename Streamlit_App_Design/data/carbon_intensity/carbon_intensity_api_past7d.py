# This module fetches hourly carbon intensity data (gCO2eq/kWh) for the past 7 days
# from the Electricity Maps API for any Australian NEM region (NSW, VIC, QLD, SA, TAS, WA, NT).

# Key features:
# - Single API call to retrieve 7 days of hourly data (~168 records)
# - Automatic conversion from UTC to local Australian time

# ------------------------------------------------------------------------------------------------

import requests
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

API_KEY = "6RnXGDnACcJRjhhzKd9P"

# Map short region names (user input) to Electricity Maps API zone codes
REGION_MAP = {
    "NSW": "AU-NSW",
    "VIC": "AU-VIC",
    "QLD": "AU-QLD",
    "SA":  "AU-SA",
    "TAS": "AU-TAS",
    "WA":  "AU-WA",
    "NT":  "AU-NT",
}

# Map API zone codes to their respective local Australian timezones
# This is needed to convert UTC timestamps to local time
REGION_TIMEZONES = {
    "AU-NSW": "Australia/Sydney",      # UTC+10 (or UTC+11 during daylight saving)
    "AU-VIC": "Australia/Melbourne",   # UTC+10 (or UTC+11 during daylight saving)
    "AU-QLD": "Australia/Brisbane",    # UTC+10 (no daylight saving)
    "AU-SA":  "Australia/Adelaide",    # UTC+9:30 (or UTC+10:30 during daylight saving)
    "AU-TAS": "Australia/Hobart",      # UTC+10 (or UTC+11 during daylight saving)
    "AU-WA":  "Australia/Perth",       # UTC+8 (no daylight saving)
    "AU-NT":  "Australia/Darwin",      # UTC+9:30 (no daylight saving)
}

def fetch_carbon_intensity_7d(region: str) -> dict:
    """
    Fetches hourly carbon intensity data for the past 7 days
    for an Australian region via the Electricity Maps API.
    Timestamps are converted from UTC to local Australian time.

    Parameters:
        region: Short region name, e.g. "NSW", "VIC", ...

    Returns:
        dict with keys:
            "region"   -> API zone code (e.g. "AU-NSW")
            "timezone" -> local timezone string (e.g. "Australia/Sydney")
            "data"     -> list of dicts with {datetime, carbon_intensity}
            "error"    -> error message (if something went wrong)
    """
    # Convert user input to uppercase and look up the API zone code
    region_code = REGION_MAP.get(region.upper())
    if not region_code:
        return {"error": f"Unknown region: '{region}'. Valid options: {list(REGION_MAP.keys())}"}

    # Calculate the time range: now minus 7 days
    now   = datetime.now(timezone.utc)  # Current time in UTC
    start = now - timedelta(days=7)     # 7 days ago in UTC

    # Build the query parameters for the API request
    params = {
        "zone":  region_code,
        "start": start.strftime("%Y-%m-%dT%H:00:00Z"),
        "end":   now.strftime("%Y-%m-%dT%H:00:00Z"),
    }

    url     = "https://api.electricitymap.org/v4/carbon-intensity/past-range"
    headers = {"auth-token": API_KEY}

    # Get the local timezone name for this region (e.g. "Australia/Sydney")
    tz_name = REGION_TIMEZONES.get(region_code)

    # Create a ZoneInfo object for timezone conversion
    local_tz = ZoneInfo(tz_name)

    try:
        # Send GET request to the API with timeout of 10 seconds
        response = requests.get(url, headers=headers, params=params, timeout=10)

        if response.status_code != 200:
            return {"error": f"API error {response.status_code}: {response.text}"}

        # Parse the JSON response into a Python dictionary
        raw = response.json()

        # Initialize empty list to store the cleaned hourly records
        hourly_records = []
        for entry in raw.get("data", []):
            # Get the UTC datetime string from API (e.g. "2026-04-02T07:00:00.000Z")
            # Replace "Z" with "+00:00" to make it parseable by fromisoformat()
            utc_dt = datetime.fromisoformat(entry.get("datetime").replace("Z", "+00:00"))
            # Convert the UTC datetime to the local Australian timezone
            # Example: 2026-04-02T07:00:00 UTC → 2026-04-02T17:00:00 Australia/Sydney (UTC+10)
            local_dt = utc_dt.astimezone(local_tz)

            # Add a cleaned record with only the fields we need
            hourly_records.append({
                "datetime":         local_dt.strftime("%Y-%m-%dT%H:%M:%S"),
                "carbon_intensity": entry.get("carbonIntensity"),
            })

        return {
            "region":   region_code,
            "timezone": tz_name,
            "data":     hourly_records,
        }

    # Catch any unexpected errors (network issues, JSON parsing errors, etc.)
    except Exception as e:
        return {"error": str(e)}
