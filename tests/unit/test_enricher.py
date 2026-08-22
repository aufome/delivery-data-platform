"""
Tests for weather parsing and enrichment logic.
"""

import json
from pathlib import Path

import pandas as pd

from enrichment.enricher import enrich_delivery_data, parse_weather_json


def test_parse_weather_json(tmp_path: Path):
    json_path = tmp_path / "raw_weather.json"
    mock_data = [
        {
            "_request": {"date": "2022-03-15", "latitude": 12.97, "longitude": 77.59},
            "hourly": {
                "time": ["2022-03-15T00:00", "2022-03-15T01:00"],
                "temperature_2m": [20.5, 21.0],
                "precipitation": [0.0, 0.1],
                "wind_speed_10m": [5.0, 5.5],
                "relative_humidity_2m": [60, 65],
            }
        }
    ]
    json_path.write_text(json.dumps(mock_data))

    df = parse_weather_json(json_path)

    assert len(df) == 2
    assert df.loc[0, "req_date"] == "2022-03-15"
    assert df.loc[0, "temperature"] == 20.5
    assert df.loc[0, "join_date"] == "2022-03-15"
    assert df.loc[0, "join_hour"] == 0

    assert df.loc[1, "join_hour"] == 1
    assert df.loc[1, "precipitation"] == 0.1


def test_enrich_delivery_data():
    delivery_df = pd.DataFrame({
        "id": [1, 2],
        "order_date": ["2022-03-15", "2022-03-15"],
        "order_hour": [0.0, 1.0],  # pandas might cast it to float if there were NaNs
        "restaurant_latitude": [12.971, 12.974],
        "restaurant_longitude": [77.592, 77.593],
    })

    weather_df = pd.DataFrame({
        "join_date": ["2022-03-15", "2022-03-15"],
        "join_hour": [0, 1],
        "req_lat": [12.97, 12.97], # Note the rounding matches
        "req_lon": [77.59, 77.59],
        "temperature": [20.5, 21.0],
    })

    enriched = enrich_delivery_data(delivery_df, weather_df)

    assert len(enriched) == 2
    assert "temperature" in enriched.columns
    assert enriched.loc[0, "temperature"] == 20.5
    assert enriched.loc[1, "temperature"] == 21.0

    # Internal join columns should be dropped
    assert "join_date" not in enriched.columns
    assert "req_lat" not in enriched.columns


def test_enrich_handles_missing_weather():
    delivery_df = pd.DataFrame({
        "id": [1],
        "order_date": ["2022-03-15"],
        "order_hour": [15.0],
        "restaurant_latitude": [12.97],
        "restaurant_longitude": [77.59],
    })

    # Empty weather
    weather_df = pd.DataFrame()

    enriched = enrich_delivery_data(delivery_df, weather_df)

    assert len(enriched) == 1
    # Since weather was empty, it won't have temperature column appended by merge
    assert "temperature" not in enriched.columns
