"""
Platform-wide configuration using pydantic-settings.

All settings are loaded from environment variables (or a .env file).
No secrets are hardcoded here. See .env.example for the full list of
required variables.

Usage:
    from config.settings import settings

    print(settings.aws_region)
    print(settings.s3_bucket_name)
"""

from enum import StrEnum
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    DEV = "dev"
    PROD = "prod"


class Settings(BaseSettings):
    """
    Central configuration object.

    Values are resolved in this priority order:
    1. Environment variables
    2. .env file (if present)
    3. Default values defined here
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Environment ──────────────────────────────────────────────────────────
    environment: Environment = Field(
        default=Environment.DEV,
        description="Deployment environment (dev | prod).",
    )

    # ── AWS ──────────────────────────────────────────────────────────────────
    aws_region: str = Field(
        default="eu-central-1",
        description="AWS region for all resources.",
    )
    aws_profile: str | None = Field(
        default=None,
        description="Named AWS CLI profile. Leave unset to use the default credential chain.",
    )

    # ── S3 ───────────────────────────────────────────────────────────────────
    s3_bucket_name: str = Field(
        description="Primary S3 data lake bucket name.",
    )

    # S3 zone prefixes — intentionally not overridable to enforce the
    # lake zone convention defined in the architecture guide.
    s3_raw_prefix: str = "raw"
    s3_validated_prefix: str = "validated"
    s3_processed_prefix: str = "processed"
    s3_analytics_prefix: str = "analytics"

    # ── Kaggle ───────────────────────────────────────────────────────────────
    kaggle_username: str = Field(
        description="Kaggle account username for API authentication.",
    )
    kaggle_key: str = Field(
        description="Kaggle API key.",
    )

    # Dataset identifier on Kaggle
    kaggle_dataset: str = Field(
        default="saurabhbadole/zomato-delivery-operations-analytics-dataset",
        description="Kaggle dataset slug (owner/dataset-name).",
    )

    # ── Weather API (Phase 5 — Open-Meteo) ───────────────────────────────────
    weather_api_key: str | None = Field(
        default=None,
        description="API key for the historical weather provider (not required for free tier Open-Meteo).",
    )
    weather_api_base_url: str = Field(
        default="https://archive-api.open-meteo.com/v1/archive",
        description="Base URL for the historical weather provider API.",
    )

    # ── Computed helpers ──────────────────────────────────────────────────────
    @property
    def is_production(self) -> bool:
        return self.environment == Environment.PROD

    def s3_raw_path(self, *parts: str) -> str:
        """Return a full S3 key under the raw zone."""
        segments = [self.s3_raw_prefix, *parts]
        return "/".join(s.strip("/") for s in segments)

    def s3_validated_path(self, *parts: str) -> str:
        """Return a full S3 key under the validated zone."""
        segments = [self.s3_validated_prefix, *parts]
        return "/".join(s.strip("/") for s in segments)

    def s3_processed_path(self, *parts: str) -> str:
        """Return a full S3 key under the processed zone."""
        segments = [self.s3_processed_prefix, *parts]
        return "/".join(s.strip("/") for s in segments)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return a cached Settings instance.

    Use this function instead of instantiating Settings directly so that
    environment variables are only parsed once per process.

    In tests, call ``get_settings.cache_clear()`` before and after
    monkeypatching environment variables to ensure a fresh instance.
    """
    return Settings()  # type: ignore[call-arg]  # fields are injected from env vars


def _lazy_settings() -> "Settings":
    """Deferred accessor used by the module-level ``settings`` proxy."""
    return get_settings()


class _SettingsProxy:
    """
    Thin proxy that defers Settings construction until first attribute access.

    This prevents import-time failures when required environment variables
    are not yet set (e.g., during test collection with monkeypatch).
    """

    _instance: Settings | None = None

    def _get(self) -> Settings:
        if self._instance is None:
            self._instance = get_settings()
        return self._instance

    def __getattr__(self, name: str) -> object:
        return getattr(self._get(), name)

    def __repr__(self) -> str:  # pragma: no cover
        return repr(self._get())


# Convenience singleton — import this in application code.
# The proxy defers construction until the first attribute is accessed,
# so importing this module never raises a ValidationError.
settings: Settings = _SettingsProxy()  # type: ignore[assignment]
