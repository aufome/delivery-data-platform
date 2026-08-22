"""
Expected schema for the Zomato delivery operations dataset.

Source:
    https://www.kaggle.com/datasets/saurabhbadole/zomato-delivery-operations-analytics-dataset

Column names are taken from the raw CSV as-is, including the unusual
``Time_taken (min)`` column name that contains spaces and parentheses.

This module defines constants only. No pandas or IO operations here.
"""

SCHEMA_VERSION = "1.0"

# All columns expected to be present in the raw CSV.
# Presence is checked; order does not matter.
EXPECTED_COLUMNS: list[str] = [
    "ID",
    "Delivery_person_ID",
    "Delivery_person_Age",
    "Delivery_person_Ratings",
    "Restaurant_latitude",
    "Restaurant_longitude",
    "Delivery_location_latitude",
    "Delivery_location_longitude",
    "Order_Date",
    "Time_Orderd",
    "Time_Order_picked",
    "Weather_conditions",
    "Road_traffic_density",
    "Vehicle_condition",
    "Type_of_order",
    "Type_of_vehicle",
    "multiple_deliveries",
    "Festival",
    "City",
    "Time_taken (min)",
]

# Column used as the primary identifier for each delivery record.
PRIMARY_KEY_COLUMN = "ID"

# Delivery duration target column.
# Note: raw values in this dataset are stored as "(24) " — digits wrapped
# in parentheses with a trailing space. Extraction happens in Phase 4.
DELIVERY_TIME_COLUMN = "Time_taken (min)"

# Coordinate columns mapped to their valid [min, max] ranges.
COORDINATE_COLUMNS: dict[str, tuple[float, float]] = {
    "Restaurant_latitude": (-90.0, 90.0),
    "Restaurant_longitude": (-180.0, 180.0),
    "Delivery_location_latitude": (-90.0, 90.0),
    "Delivery_location_longitude": (-180.0, 180.0),
}

# Date columns that must be parseable.
DATE_COLUMNS: list[str] = ["Order_Date"]

# Time columns that must match HH:MM or HH:MM:SS.
TIME_COLUMNS: list[str] = ["Time_Orderd", "Time_Order_picked"]

# Known categorical domains.
# Unexpected values are flagged as warnings (domain may be incomplete).
CATEGORICAL_DOMAINS: dict[str, set[str]] = {
    "Weather_conditions": {"Fog", "Stormy", "Sandstorms", "Windy", "Cloudy", "Sunny"},
    "Road_traffic_density": {"Low", "Medium", "High", "Jam"},
    "Type_of_vehicle": {"motorcycle", "scooter", "electric_scooter", "bicycle"},
    "Type_of_order": {"Snack", "Meal", "Drinks", "Buffet"},
    "Festival": {"Yes", "No"},
    "City": {"Metropolitian", "Urban", "Semi-Urban"},
}
