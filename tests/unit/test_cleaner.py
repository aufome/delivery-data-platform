"""
Unit tests for processing.cleaner.
"""

import numpy as np
import pandas as pd
import pytest

from processing.cleaner import (
    calculate_haversine_distance,
    calculate_temporal_features,
    clean_delivery_duration,
    clean_numeric_columns,
    rename_and_format_columns,
)


@pytest.fixture
def sample_raw_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ID": ["1", "2", "3"],
            "Delivery_person_Age": ["25", "NaN", "30"],
            "Delivery_person_Ratings": ["4.5", " NaN ", "3.8"],
            "Vehicle_condition": ["1", "2", "NaN"],
            "multiple_deliveries": ["0", "1", "NaN"],
            "Time_taken (min)": ["(24) ", "25.5", "NaN"],
            "Restaurant_latitude": [12.9716, 12.9716, np.nan],
            "Restaurant_longitude": [77.5946, 77.5946, np.nan],
            "Delivery_location_latitude": [12.9816, 12.9816, np.nan],
            "Delivery_location_longitude": [77.6046, 77.6046, np.nan],
            "Order_Date": ["15-03-2022", "16-03-2022", "invalid_date"],
            "Time_Orderd": ["10:30", "23:50", "NaN"],
            "Time_Order_picked": ["10:45", "00:10", "NaN"],  # 00:10 is next day pick up
            "Weather_conditions": [" Sunny ", "NaN", "Fog"],
            "Road_traffic_density": ["Medium", " Low ", "NaN"],
        }
    )


class TestCleanNumericColumns:
    def test_handles_nan_strings_and_strips(self, sample_raw_df: pd.DataFrame) -> None:
        df = clean_numeric_columns(sample_raw_df)
        assert pd.isna(df.loc[1, "Delivery_person_Age"])
        assert df.loc[0, "Delivery_person_Age"] == 25.0
        assert pd.isna(df.loc[1, "Delivery_person_Ratings"])
        assert df.loc[0, "Delivery_person_Ratings"] == 4.5


class TestCleanDeliveryDuration:
    def test_extracts_duration_from_paren_format(self, sample_raw_df: pd.DataFrame) -> None:
        df = clean_delivery_duration(sample_raw_df)
        assert "delivery_duration" in df.columns
        assert "Time_taken (min)" not in df.columns
        assert df.loc[0, "delivery_duration"] == 24.0
        assert df.loc[1, "delivery_duration"] == 25.5
        assert pd.isna(df.loc[2, "delivery_duration"])


class TestCalculateHaversineDistance:
    def test_calculates_distance_correctly(self, sample_raw_df: pd.DataFrame) -> None:
        df = calculate_haversine_distance(sample_raw_df)
        assert "straight_line_distance" in df.columns
        # Distance between (12.9716, 77.5946) and (12.9816, 77.6046) is ~ 1.54 km
        assert np.isclose(df.loc[0, "straight_line_distance"], 1.54, atol=0.1)  # type: ignore[arg-type]
        assert pd.isna(df.loc[2, "straight_line_distance"])


class TestCalculateTemporalFeatures:
    def test_extracts_hour_day_weekend_peak(self, sample_raw_df: pd.DataFrame) -> None:
        df = calculate_temporal_features(sample_raw_df)

        # 15-03-2022 is a Tuesday (day 1)
        assert df.loc[0, "order_day_of_week"] == 1
        assert df.loc[0, "order_hour"] == 10
        assert df.loc[0, "order_month"] == 3
        assert df.loc[0, "is_weekend"] == 0
        assert df.loc[0, "is_peak_hour"] == 0  # 10 is not peak (11-14, 18-21)

        # 16-03-2022 is a Wednesday (day 2), order at 23:50 (not peak)
        assert df.loc[1, "order_day_of_week"] == 2
        assert df.loc[1, "is_peak_hour"] == 0

    def test_pickup_delay_handles_midnight_cross(self, sample_raw_df: pd.DataFrame) -> None:
        df = calculate_temporal_features(sample_raw_df)

        # 10:30 to 10:45 -> 15 min
        assert df.loc[0, "pickup_delay"] == 15.0

        # 23:50 to 00:10 -> 20 min (crossed midnight)
        assert df.loc[1, "pickup_delay"] == 20.0

    def test_invalid_dates_produce_nans(self, sample_raw_df: pd.DataFrame) -> None:
        df = calculate_temporal_features(sample_raw_df)
        assert pd.isna(df.loc[2, "order_hour"])
        assert pd.isna(df.loc[2, "pickup_delay"])


class TestRenameAndFormatColumns:
    def test_renames_to_snake_case_and_cleans_strings(self, sample_raw_df: pd.DataFrame) -> None:
        df = rename_and_format_columns(sample_raw_df)

        assert "delivery_person_age" in df.columns
        assert "weather_conditions" in df.columns

        # Strings are stripped
        assert df.loc[0, "weather_conditions"] == "Sunny"
        # NaN strings are replaced with actual NaNs
        assert pd.isna(df.loc[1, "weather_conditions"])
        assert df.loc[1, "traffic_density"] == "Low"
