import requests
import pandas as pd

CSV_DATEIEN = {
    "AU-NSW": "data/carbon_nsw.csv",
    "AU-VIC": "data/carbon_vic.csv",
    "AU-QLD": "data/carbon_qld.csv",
    "AU-SA":  "data/carbon_sa.csv",
    "AU-TAS": "data/carbon_tas.csv",
}

# Electricity Maps API Key
API_KEY = "PPkCcYvCU7dds4RUew5M"

def lade_historische_daten(region: str) -> pd.DataFrame:
    """
    Lädt historische CSV-Daten einer Region.
    """
    df = pd.read_csv(CSV_DATEIEN[region])
    df["datetime"] = pd.to_datetime(df["datetime"])
    return df.sort_values("datetime")


def baue_zukunftsdaten(stunden: int) -> pd.DataFrame:
    """
    Baut zukünftige Zeitpunkte und die drei ML-Features dazu.
    """
    future = pd.date_range(
        start=pd.Timestamp.now().floor("h"),
        periods=stunden,
        freq="h"
    )

    df = pd.DataFrame({"datetime": future})
    df["hour"] = df["datetime"].dt.hour
    df["day_of_week"] = df["datetime"].dt.dayofweek
    df["month"] = df["datetime"].dt.month
    return df


def hole_live_carbon_intensity(region: str):
    """
    Holt den aktuellsten Carbon-Intensity-Wert live aus Electricity Maps.
    """
    url = f"https://api.electricitymap.org/v3/carbon-intensity/latest?zone={region}"
    headers = {"auth-token": API_KEY}

    try:
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code != 200:
            return None

        data = response.json()

        return {
            "region": region,
            "datetime": data.get("datetime"),
            "carbon_intensity": data.get("carbonIntensity")
        }

    except Exception:
        return None
    