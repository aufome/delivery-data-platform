"""
check_env.py — Local environment health check.

Run this script to verify that all required environment variables are
present before starting the pipeline. Prints a clear summary and exits
with a non-zero code if anything is missing.

Usage:
    uv run python scripts/check_env.py
"""

import sys

import structlog

from config.settings import Settings

log = structlog.get_logger()


def check_environment() -> bool:
    """
    Validate that all required settings can be loaded from the environment.

    Returns True if all checks pass, False otherwise.
    """
    print("=" * 60)
    print("  Delivery Data Platform — Environment Check")
    print("=" * 60)

    errors: list[str] = []

    # Attempt to load settings — this validates all required fields.
    try:
        s = Settings()
    except Exception as exc:
        print(f"\n❌  Failed to load settings:\n    {exc}\n")
        print("    → Copy .env.example to .env and fill in the required values.")
        return False

    checks = [
        ("AWS Region", s.aws_region, None),
        ("S3 Bucket", s.s3_bucket_name, None),
        ("Kaggle Username", s.kaggle_username, None),
        ("Kaggle API Key", "***" if s.kaggle_key else "", s.kaggle_key or ""),
        (
            "Weather API Key",
            "***" if s.weather_api_key else "(not set — required from Phase 5)",
            None,  # optional for now
        ),
        ("Environment", s.environment.value, None),
    ]

    all_ok = True
    for label, display_value, raw_value in checks:
        missing = raw_value == "" if raw_value is not None else False
        status = "⚠️ " if missing else "✅"
        print(f"  {status}  {label:<20} {display_value}")
        if missing:
            errors.append(label)

    print()

    if errors:
        print(f"⚠️  {len(errors)} optional value(s) not configured:")
        for e in errors:
            print(f"    - {e}")
        print()

    print("S3 zone paths (example):")
    example_date = "ingestion_date=2024-01-01"
    print(f"  raw      → s3://{s.s3_bucket_name}/{s.s3_raw_path('delivery_orders', example_date)}")
    print(f"  validated→ s3://{s.s3_bucket_name}/{s.s3_validated_path('delivery_orders')}")
    print(f"  processed→ s3://{s.s3_bucket_name}/{s.s3_processed_path('enriched')}")
    print()

    if not all_ok:
        print("❌  Environment check failed.")
    else:
        print("✅  Environment looks good. Happy engineering!")

    print("=" * 60)
    return all_ok


if __name__ == "__main__":
    ok = check_environment()
    sys.exit(0 if ok else 1)
