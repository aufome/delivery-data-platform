"""
Open-Meteo Historical API Client.

Fetches historical weather data using geographic coordinates.
Includes basic retry logic for resilience against transient network issues
and rate limits.
"""

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from config.settings import get_settings

logger = logging.getLogger(__name__)


class WeatherAPIError(Exception):
    """Raised when the weather API fails after retries or returns a non-200 status."""
    pass


def fetch_historical_weather(
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
    max_retries: int = 3,
    backoff_factor: float = 1.0,
) -> dict[str, Any]:
    """
    Fetch hourly historical weather data for a given coordinate and date range.
    
    Args:
        latitude: Geographic latitude.
        longitude: Geographic longitude.
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date in YYYY-MM-DD format.
        max_retries: Maximum number of retry attempts.
        backoff_factor: Multiplier for exponential backoff.
        
    Returns:
        The raw JSON response parsed into a dict.
    """
    settings = get_settings()
    base_url = settings.weather_api_base_url

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m",
        "timezone": "UTC",
    }

    query_string = urllib.parse.urlencode(params)
    url = f"{base_url}?{query_string}"

    for attempt in range(1, max_retries + 1):
        try:
            logger.info("weather.api.request", extra={"url": url, "attempt": attempt})
            req = urllib.request.Request(url, headers={"User-Agent": "DeliveryDataPlatform/1.0"})
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status != 200:
                    raise urllib.error.HTTPError(
                        url, response.status, "Non-200 response", response.headers, None
                    )
                data = json.loads(response.read().decode("utf-8"))
                return data

        except (urllib.error.URLError, json.JSONDecodeError) as e:
            logger.warning(
                "weather.api.failed",
                extra={"error": str(e), "attempt": attempt, "max_retries": max_retries}
            )
            if attempt == max_retries:
                raise WeatherAPIError(f"Failed to fetch weather data after {max_retries} attempts: {e}") from e

            time.sleep(backoff_factor * (2 ** (attempt - 1)))

    raise WeatherAPIError("Unexpected exit from retry loop")
