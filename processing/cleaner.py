"""
Data cleaning and feature engineering logic for Phase 4.

This module contains pure functions to transform the raw delivery dataset
into a clean, standardized format suitable for analytical processing and ML.
It uses pandas for vectorized operations.
"""

import numpy as np
import pandas as pd


def clean_numeric_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean columns that should be numeric but often contain string artifacts.
    Handles standard string cleaning (stripping) and converting 'NaN' strings to actual NaNs.
    """
    out = df.copy()
    numeric_cols = [
        "Delivery_person_Age",
        "Delivery_person_Ratings",
        "Vehicle_condition",
        "multiple_deliveries",
    ]
    for col in numeric_cols:
        if col in out.columns:
            # Handle possible string 'NaN' or empty spaces
            if out[col].dtype == object:
                out[col] = out[col].astype(str).str.strip().replace("NaN", np.nan)
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def clean_delivery_duration(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract delivery duration from the 'Time_taken (min)' column.
    Handles the raw '(24) ' format by extracting digits.
    """
    out = df.copy()
    col = "Time_taken (min)"
    if col in out.columns:
        if pd.api.types.is_numeric_dtype(out[col]):
            out["delivery_duration"] = pd.to_numeric(out[col], errors="coerce")
        else:
            # Extract digits and decimals from strings like '(24) ' or '24.5'
            extracted = out[col].astype(str).str.extract(r"(\d+(?:\.\d+)?)")[0]
            out["delivery_duration"] = pd.to_numeric(extracted, errors="coerce")
        out = out.drop(columns=[col])
    return out


def calculate_haversine_distance(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate the straight-line (Haversine) distance between the restaurant
    and delivery locations in kilometers.
    """
    out = df.copy()

    # Earth radius in kilometers
    R = 6371.0

    lat1 = np.radians(pd.to_numeric(out["Restaurant_latitude"], errors="coerce"))
    lon1 = np.radians(pd.to_numeric(out["Restaurant_longitude"], errors="coerce"))
    lat2 = np.radians(pd.to_numeric(out["Delivery_location_latitude"], errors="coerce"))
    lon2 = np.radians(pd.to_numeric(out["Delivery_location_longitude"], errors="coerce"))

    dlon = lon2 - lon1
    dlat = lat2 - lat1

    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2.0) ** 2
    # Ensure values are within [0, 1] due to floating point inaccuracies
    a = np.clip(a, 0.0, 1.0)
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))

    out["straight_line_distance"] = R * c
    return out


def calculate_temporal_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Parse order datetime and calculate temporal features:
    - order_hour, order_day_of_week, order_month
    - is_weekend, is_peak_hour
    - pickup_delay (minutes between Orderd and Picked)
    """
    out = df.copy()

    # Parse Order_Date (DD-MM-YYYY)
    order_date = pd.to_datetime(out["Order_Date"], format="%d-%m-%Y", errors="coerce")

    # Parse times. They could be HH:MM or HH:MM:SS, but usually just strings.
    # Combine date and time for full timestamp
    time_ordered_str = (
        out.get("Time_Orderd", pd.Series(dtype=str))
        .astype(str)
        .str.strip()
        .replace(["NaN", "nan", "None", ""], np.nan)
    )
    time_picked_str = (
        out.get("Time_Order_picked", pd.Series(dtype=str))
        .astype(str)
        .str.strip()
        .replace(["NaN", "nan", "None", ""], np.nan)
    )

    # Convert to timedelta
    time_ordered_td = pd.to_timedelta(time_ordered_str + ":00", errors="coerce")
    time_picked_td = pd.to_timedelta(time_picked_str + ":00", errors="coerce")

    # Full datetime for order
    order_dt = order_date + time_ordered_td

    # Calculate pickup delay
    # Handle cases where pick up is the next day (e.g. ordered 23:50, picked 00:10)
    delay = (time_picked_td - time_ordered_td).dt.total_seconds() / 60.0
    # If negative, it means it crossed midnight
    delay_arr = np.where(delay < 0, delay + 24 * 60, delay)
    out["pickup_delay"] = delay_arr

    # Feature extraction
    out["order_hour"] = order_dt.dt.hour
    out["order_day_of_week"] = order_dt.dt.dayofweek  # 0=Monday, 6=Sunday
    out["order_month"] = order_dt.dt.month
    out["is_weekend"] = out["order_day_of_week"].isin([5, 6]).astype(int)

    # Peak hours: assuming 11-14 (lunch) and 18-21 (dinner)
    hour = out["order_hour"]
    out["is_peak_hour"] = ((hour >= 11) & (hour <= 14)) | ((hour >= 18) & (hour <= 21))
    out["is_peak_hour"] = out["is_peak_hour"].astype(int)

    # Handle NaNs for boolean/int features where datetime was invalid
    missing_dt_mask = order_dt.isna()
    for col in ["order_hour", "order_day_of_week", "order_month", "is_weekend", "is_peak_hour"]:
        out.loc[missing_dt_mask, col] = np.nan

    return out


def rename_and_format_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardize column names to snake_case.
    Removes the old raw columns if they were replaced by new feature columns,
    but for this dataset we'll keep and rename the original ones as well.
    """
    out = df.copy()

    # Clean string categorical columns (strip spaces, handle 'NaN' string)
    cat_cols = [
        "Weather_conditions",
        "Road_traffic_density",
        "Type_of_order",
        "Type_of_vehicle",
        "Festival",
        "City",
    ]
    for col in cat_cols:
        if col in out.columns:
            out[col] = out[col].astype(str).str.strip().replace(["NaN", "nan", "None", ""], np.nan)

    rename_map = {
        "ID": "id",
        "Delivery_person_ID": "delivery_person_id",
        "Delivery_person_Age": "delivery_person_age",
        "Delivery_person_Ratings": "delivery_person_ratings",
        "Restaurant_latitude": "restaurant_latitude",
        "Restaurant_longitude": "restaurant_longitude",
        "Delivery_location_latitude": "delivery_location_latitude",
        "Delivery_location_longitude": "delivery_location_longitude",
        "Order_Date": "order_date",
        "Time_Orderd": "time_ordered",
        "Time_Order_picked": "time_order_picked",
        "Weather_conditions": "weather_conditions",
        "Road_traffic_density": "traffic_density",
        "Vehicle_condition": "vehicle_condition",
        "Type_of_order": "type_of_order",
        "Type_of_vehicle": "type_of_vehicle",
        "multiple_deliveries": "multiple_deliveries",
        "Festival": "festival",
        "City": "city",
    }

    out = out.rename(columns=rename_map)
    return out


def process_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Master pipeline for data processing and feature engineering.
    """
    df = clean_numeric_columns(df)
    df = clean_delivery_duration(df)
    df = calculate_haversine_distance(df)
    df = calculate_temporal_features(df)
    df = rename_and_format_columns(df)

    return df
