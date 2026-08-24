"""
Weather ingestion logic.

Extracts unique coordinates from the processed delivery data, fetches historical
weather data for those coordinates and dates, and saves the raw JSON responses
to the S3 raw/weather zone.
"""

import json
import logging
import tempfile
from pathlib import Path

import pandas as pd

from config.settings import get_settings
from enrichment.openmeteo_client import fetch_historical_weather
from processing.s3_client import upload_file

logger = logging.getLogger(__name__)


def ingest_weather_for_orders(
    processed_df: pd.DataFrame,
    ingestion_date: str,
    dry_run: bool = False,
) -> Path | None:
    """
    Extract unique dates and rounded coordinates from the dataframe, fetch weather,
    and save the combined raw responses to S3.

    Returns:
        The path to the local raw JSON file if created, or None if skipped/failed.
    """
    settings = get_settings()

    # We round coordinates to 2 decimal places to group nearby restaurants and reduce API calls.
    # ~1.1km resolution is sufficient for weather data.
    if "restaurant_latitude" not in processed_df.columns or "order_date" not in processed_df.columns:
        logger.warning("weather.ingestion.missing_columns")
        return None

    # Filter out null coordinates and dates
    df_valid = processed_df.dropna(subset=["restaurant_latitude", "restaurant_longitude", "order_date"]).copy()
    if df_valid.empty:
        logger.warning("weather.ingestion.no_valid_data")
        return None

    df_valid["lat_round"] = df_valid["restaurant_latitude"].round(2)
    df_valid["lon_round"] = df_valid["restaurant_longitude"].round(2)

    # Format dates as YYYY-MM-DD for the API
    df_valid["date_str"] = pd.to_datetime(df_valid["order_date"]).dt.strftime("%Y-%m-%d")

    unique_requests = df_valid[["date_str", "lat_round", "lon_round"]].drop_duplicates()
    logger.info("weather.ingestion.planned_requests", count=len(unique_requests))

    # In a real large-scale system with thousands of coordinates, this should be distributed
    # (e.g., via Airflow mapped tasks). For this dataset (a few distinct cities), sequential is fine.
    # To prevent blowing up the API in this demo, we can limit it or process them sequentially.
    # Wait, the dataset might span many days. Let's group by date and get min/max coordinates?
    # No, we fetch exactly what's needed.

    all_responses = []

    for _, row in unique_requests.iterrows():
        date = row["date_str"]
        lat = row["lat_round"]
        lon = row["lon_round"]

        try:
            data = fetch_historical_weather(
                latitude=lat,
                longitude=lon,
                start_date=date,
                end_date=date,
            )
            # Annotate response with requested params to facilitate joining later
            data["_request"] = {
                "date": date,
                "latitude": lat,
                "longitude": lon,
            }
            all_responses.append(data)
        except Exception as e:
            logger.error("weather.ingestion.fetch_failed", error=str(e), date=date, lat=lat, lon=lon)
            # Continue fetching others even if one fails

    if not all_responses:
        logger.error("weather.ingestion.all_failed")
        return None

    # Write to a temporary file
    tmp_dir = Path(tempfile.mkdtemp(prefix="ddp_weather_"))
    out_file = tmp_dir / "raw_weather.json"

    with out_file.open("w", encoding="utf-8") as f:
        json.dump(all_responses, f)

    logger.info("weather.ingestion.saved_locally", path=str(out_file), count=len(all_responses))

    if not dry_run:
        s3_key = f"{settings.s3_raw_path('weather')}/source=openmeteo/ingestion_date={ingestion_date}/weather_data.json"
        upload_file(
            local_path=out_file,
            bucket=settings.s3_bucket_name,
            s3_key=s3_key,
            region=settings.aws_region,
        )
        logger.info("weather.ingestion.uploaded", s3_key=s3_key)

    return out_file
