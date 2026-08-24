"""
Advanced Data Observability Module.

In a production environment, data can silently drift or break (e.g., temperatures
suddenly reading 1000 degrees, or distances becoming negative). This module runs
post-processing assertions to ensure data quality before feeding it to the ML model.
"""

import logging

import pandas as pd

logger = logging.getLogger(__name__)


class DataQualityError(Exception):
    """Raised when data fails observability checks."""
    pass


def run_observability_checks(df: pd.DataFrame) -> None:
    """
    Run data quality checks against the enriched dataset.
    Similar to Great Expectations or Soda, but lightweight.
    """
    logger.info("Running Data Observability Checks...")
    errors = []

    # 1. Freshness & Nulls Check
    null_counts = df.isnull().sum()
    if null_counts["order_date"] > 0:
        errors.append(f"Critical: Found {null_counts['order_date']} missing order dates.")

    if null_counts["delivery_duration"] > 0:
        errors.append(f"Data loss: {null_counts['delivery_duration']} records are missing target delivery_duration.")

    # 2. Anomaly / Outlier Check (Distance)
    # Haversine distance shouldn't be negative, and shouldn't be > 100km for a food delivery
    if (df["straight_line_distance"] < 0).any():
        errors.append("Anomaly: Negative delivery distance detected.")

    max_dist = df["straight_line_distance"].max()
    if max_dist > 100:
        errors.append(f"Anomaly: Suspicious max distance of {max_dist:.2f}km detected. Is this food delivery?")

    # 3. Weather Data Quality Check
    # Temperature ranges on Earth shouldn't exceed typical human survivable limits for deliveries
    if "temperature" in df.columns:
        if (df["temperature"] > 60).any() or (df["temperature"] < -50).any():
            errors.append("Data Drift: Extreme temperature values outside normal planetary limits detected.")

    if errors:
        for error in errors:
            logger.error("OBSERVABILITY ALERT: %s", error)
        raise DataQualityError(f"Data Observability checks failed with {len(errors)} errors.")

    logger.info("Data Observability checks passed successfully!")
