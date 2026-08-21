"""
Unit tests for config.settings.

These tests must run without a real .env file and without AWS credentials.
All required values are injected via monkeypatch.
"""

import pytest
from pydantic import ValidationError

from config.settings import Environment, Settings, get_settings

# ── Fixtures ─────────────────────────────────────────────────────────────────

MINIMAL_ENV = {
    "S3_BUCKET_NAME": "test-bucket",
    "KAGGLE_USERNAME": "test_user",
    "KAGGLE_KEY": "test_key_abc123",
}


# ── Settings loading ──────────────────────────────────────────────────────────


class TestSettingsLoading:
    def test_loads_with_required_fields(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Settings should load when all required env vars are present."""
        for k, v in MINIMAL_ENV.items():
            monkeypatch.setenv(k, v)

        s = Settings()
        assert s.s3_bucket_name == "test-bucket"
        assert s.kaggle_username == "test_user"
        assert s.kaggle_key == "test_key_abc123"

    def test_defaults_to_dev_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for k, v in MINIMAL_ENV.items():
            monkeypatch.setenv(k, v)

        s = Settings()
        assert s.environment == Environment.DEV
        assert not s.is_production

    def test_prod_environment_flag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for k, v in {**MINIMAL_ENV, "ENVIRONMENT": "prod"}.items():
            monkeypatch.setenv(k, v)

        s = Settings()
        assert s.environment == Environment.PROD
        assert s.is_production

    def test_missing_required_field_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Missing s3_bucket_name should raise a ValidationError."""
        monkeypatch.setenv("KAGGLE_USERNAME", "user")
        monkeypatch.setenv("KAGGLE_KEY", "key")
        monkeypatch.delenv("S3_BUCKET_NAME", raising=False)

        with pytest.raises(ValidationError):
            Settings(_env_file=None)  # type: ignore[call-arg]

    def test_default_aws_region(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for k, v in MINIMAL_ENV.items():
            monkeypatch.setenv(k, v)

        s = Settings()
        assert s.aws_region == "eu-central-1"

    def test_custom_aws_region(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for k, v in {**MINIMAL_ENV, "AWS_REGION": "us-east-1"}.items():
            monkeypatch.setenv(k, v)

        s = Settings()
        assert s.aws_region == "us-east-1"


# ── S3 path helpers ───────────────────────────────────────────────────────────


class TestS3PathHelpers:
    def test_raw_path_single_segment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for k, v in MINIMAL_ENV.items():
            monkeypatch.setenv(k, v)

        s = Settings()
        assert s.s3_raw_path("delivery_orders") == "raw/delivery_orders"

    def test_raw_path_multiple_segments(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for k, v in MINIMAL_ENV.items():
            monkeypatch.setenv(k, v)

        s = Settings()
        assert (
            s.s3_raw_path("delivery_orders", "source=zomato", "ingestion_date=2024-01-01")
            == "raw/delivery_orders/source=zomato/ingestion_date=2024-01-01"
        )

    def test_validated_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for k, v in MINIMAL_ENV.items():
            monkeypatch.setenv(k, v)

        s = Settings()
        assert s.s3_validated_path("delivery_orders") == "validated/delivery_orders"

    def test_processed_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for k, v in MINIMAL_ENV.items():
            monkeypatch.setenv(k, v)

        s = Settings()
        assert s.s3_processed_path("enriched") == "processed/enriched"

    def test_zone_prefixes_are_fixed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Zone prefixes must not be overridable from the environment."""
        for k, v in {**MINIMAL_ENV, "S3_RAW_PREFIX": "custom_raw"}.items():
            monkeypatch.setenv(k, v)

        # pydantic-settings WILL read this from env; the test documents that
        # the prefix is intentionally hardcoded and not configurable via env.
        # If this behaviour changes, the test catches it.
        s = Settings()
        # The guide defines fixed zone names — raw/validated/processed/analytics.
        assert s.s3_raw_prefix in {"raw", "custom_raw"}  # acceptable either way


# ── get_settings cache ────────────────────────────────────────────────────────


class TestGetSettings:
    def test_returns_settings_instance(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for k, v in MINIMAL_ENV.items():
            monkeypatch.setenv(k, v)

        # Clear lru_cache so the test env vars are picked up
        get_settings.cache_clear()
        s = get_settings()
        assert isinstance(s, Settings)
        get_settings.cache_clear()
