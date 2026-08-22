"""
Tests for openmeteo_client.
"""

import json
import urllib.error
from unittest import mock

import pytest

from enrichment.openmeteo_client import WeatherAPIError, fetch_historical_weather


@pytest.fixture
def mock_urlopen():
    with mock.patch("urllib.request.urlopen") as m:
        yield m


def test_fetch_success(mock_urlopen, settings_env):
    mock_resp = mock.MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = json.dumps({"hourly": {"temperature_2m": [20.5]}}).encode("utf-8")
    mock_urlopen.return_value.__enter__.return_value = mock_resp

    data = fetch_historical_weather(12.97, 77.59, "2022-03-15", "2022-03-15")
    assert data["hourly"]["temperature_2m"] == [20.5]
    mock_urlopen.assert_called_once()


def test_fetch_retries_on_http_error(mock_urlopen, settings_env):
    # Fail twice, succeed on third
    bad_resp = mock.MagicMock()
    bad_resp.status = 500

    good_resp = mock.MagicMock()
    good_resp.status = 200
    good_resp.read.return_value = json.dumps({"success": True}).encode("utf-8")

    # We raise URLError for 500s according to urllib behavior, or we raise HTTPError explicitly in our code
    mock_urlopen.side_effect = [
        urllib.error.URLError("500"),
        urllib.error.URLError("502"),
        mock.MagicMock(__enter__=mock.MagicMock(return_value=good_resp))
    ]

    with mock.patch("time.sleep"):  # skip actual sleep
        data = fetch_historical_weather(12.97, 77.59, "2022-03-15", "2022-03-15", max_retries=3)

    assert data["success"] is True
    assert mock_urlopen.call_count == 3


def test_fetch_exhausts_retries(mock_urlopen, settings_env):
    mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

    with mock.patch("time.sleep"):
        with pytest.raises(WeatherAPIError, match="Failed to fetch weather data after 2 attempts"):
            fetch_historical_weather(12.97, 77.59, "2022-03-15", "2022-03-15", max_retries=2)
