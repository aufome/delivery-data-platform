"""
Weather enrichment logic.

Parses raw Open-Meteo JSON responses and merges them with the processed
delivery DataFrame based on date, hour, and location.
"""

import json
from pathlib import Path

import pandas as pd


def parse_weather_json(json_path: Path) -> pd.DataFrame:
    """
    Parse the combined raw JSON responses from Open-Meteo into a flat DataFrame.

    The raw JSON contains hourly arrays. This function "unpivots" them so each
    row is a single hour for a specific coordinate.
    """
    with json_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    rows = []
    for entry in data:
        req = entry.get("_request", {})
        hourly = entry.get("hourly", {})

        times = hourly.get("time", [])
        temps = hourly.get("temperature_2m", [])
        precip = hourly.get("precipitation", [])
        wind = hourly.get("wind_speed_10m", [])
        humidity = hourly.get("relative_humidity_2m", [])

        for i, time_str in enumerate(times):
            # time_str is ISO format "2022-03-15T00:00"
            rows.append({
                "req_date": req.get("date"),
                "req_lat": req.get("latitude"),
                "req_lon": req.get("longitude"),
                "weather_time": time_str,
                "temperature": temps[i] if i < len(temps) else None,
                "precipitation": precip[i] if i < len(precip) else None,
                "wind_speed": wind[i] if i < len(wind) else None,
                "humidity": humidity[i] if i < len(humidity) else None,
            })

    df = pd.DataFrame(rows)
    if not df.empty:
        # Extract hour and date for joining
        dt = pd.to_datetime(df["weather_time"])
        df["join_date"] = dt.dt.strftime("%Y-%m-%d")
        df["join_hour"] = dt.dt.hour

    return df


def enrich_delivery_data(delivery_df: pd.DataFrame, weather_df: pd.DataFrame) -> pd.DataFrame:
    """
    Join delivery orders with weather data on date, hour, and rounded location.
    """
    out = delivery_df.copy()

    if weather_df.empty:
        return out

    # Prepare join keys on the delivery side
    out["join_date"] = pd.to_datetime(out["order_date"]).dt.strftime("%Y-%m-%d")
    out["req_lat"] = out["restaurant_latitude"].round(2)
    out["req_lon"] = out["restaurant_longitude"].round(2)
    # The order_hour is a float due to NaNs, fill or convert carefully
    out["join_hour"] = out["order_hour"].fillna(-1).astype(int)

    # Merge
    # Left join ensures we don't drop orders if weather is missing
    merged = pd.merge(
        out,
        weather_df,
        how="left",
        on=["join_date", "join_hour", "req_lat", "req_lon"]
    )

    # Drop temporary join columns and any internal weather_time column
    cols_to_drop = ["join_date", "req_lat", "req_lon", "join_hour", "weather_time"]
    merged = merged.drop(columns=[c for c in cols_to_drop if c in merged.columns])

    return merged
