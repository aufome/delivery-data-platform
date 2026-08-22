"""
Shared test fixtures for the delivery data platform test suite.
"""

import pytest


@pytest.fixture()
def aws_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Set fake AWS credentials so moto can intercept boto3 calls.

    Must be used (directly or via a dependent fixture) in any test that
    instantiates boto3 clients or uses the moto ``@mock_aws`` decorator.
    """
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-central-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")


# Minimal settings required by all modules that import config.settings.
MINIMAL_SETTINGS_ENV: dict[str, str] = {
    "S3_BUCKET_NAME": "test-bucket",
    "KAGGLE_USERNAME": "test_user",
    "KAGGLE_KEY": "test_key_abc123",
    "AWS_REGION": "eu-central-1",
    "ENVIRONMENT": "dev",
}


@pytest.fixture()
def settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Inject the minimal environment required to load Settings."""
    for k, v in MINIMAL_SETTINGS_ENV.items():
        monkeypatch.setenv(k, v)

    # Clear lru_cache so the fresh env vars are picked up.
    from config.settings import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
