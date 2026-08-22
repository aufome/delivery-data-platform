"""
Ingestion pipeline — Phase 2 entry point.

Downloads the Zomato delivery dataset from Kaggle, validates its schema,
uploads the raw file to the S3 raw zone, and writes an ingestion manifest
alongside it.

The raw file is always uploaded regardless of validation outcome — the
raw layer is immutable and validation is a separate concern. The manifest
records all violations so downstream jobs can make blocking decisions.

Usage
-----
    uv run python -m ingestion.pipeline              # full run
    uv run python -m ingestion.pipeline --dry-run   # skip S3 uploads
    uv run python -m ingestion.pipeline --local-file /path/to/delivery_data.csv
"""

import argparse
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import structlog

from config.settings import get_settings
from ingestion.kaggle_client import download_dataset
from ingestion.manifest import IngestionManifest, build_manifest
from ingestion.s3_uploader import upload_file, upload_text
from validation.rules import validate

log = structlog.get_logger(__name__)


def _build_s3_keys(
    raw_prefix: str,
    ingestion_date: str,
    filename: str = "delivery_data.csv",
) -> tuple[str, str]:
    """
    Return ``(data_key, manifest_key)`` for the given ingestion date.

    Example output for ``ingestion_date="2024-01-15"``:
        raw/delivery_orders/source=zomato/ingestion_date=2024-01-15/delivery_data.csv
        raw/delivery_orders/source=zomato/ingestion_date=2024-01-15/manifest.json
    """
    base = f"{raw_prefix}/delivery_orders/source=zomato/ingestion_date={ingestion_date}"
    return f"{base}/{filename}", f"{base}/manifest.json"


def run(
    *,
    local_file: Path | None = None,
    dry_run: bool = False,
    ingestion_timestamp: datetime | None = None,
) -> IngestionManifest:
    """
    Execute the ingestion pipeline.

    Args:
        local_file: If provided, skip the Kaggle download and use this file.
        dry_run: If True, validate and build the manifest but skip S3 uploads.
        ingestion_timestamp: Override the UTC timestamp (useful in tests).

    Returns:
        The completed ``IngestionManifest``.
    """
    s = get_settings()
    ts = ingestion_timestamp or datetime.now(UTC)
    ingestion_date = ts.strftime("%Y-%m-%d")

    log.info(
        "pipeline.start",
        environment=s.environment,
        bucket=s.s3_bucket_name,
        dry_run=dry_run,
        ingestion_date=ingestion_date,
    )

    _tmp: tempfile.TemporaryDirectory[str] | None = None

    try:
        # ── 1. Acquire the source file ─────────────────────────────────────
        if local_file is not None:
            log.info("pipeline.using_local_file", path=str(local_file))
            csv_path = local_file
        else:
            _tmp = tempfile.TemporaryDirectory(prefix="ddp_ingest_")
            csv_path = download_dataset(download_dir=Path(_tmp.name))

        # ── 2. Load into pandas to obtain row/column counts ───────────────
        log.info("pipeline.csv.reading", path=str(csv_path))
        df = pd.read_csv(csv_path, low_memory=False)
        row_count, column_count = df.shape
        log.info("pipeline.csv.loaded", rows=row_count, columns=column_count)

        # ── 3. Schema and rule validation ─────────────────────────────────
        log.info("pipeline.validation.start")
        result = validate(df)
        log.info(
            "pipeline.validation.complete",
            passed=result.passed,
            errors=len(result.errors),
            warnings=len(result.warnings),
        )
        for v in result.violations:
            if v.severity == "error":
                log.error(
                    "pipeline.validation.violation",
                    check=v.check,
                    column=v.column,
                    detail=v.detail,
                )
            else:
                log.warning(
                    "pipeline.validation.violation",
                    check=v.check,
                    column=v.column,
                    detail=v.detail,
                )

        # ── 4. Build S3 keys ───────────────────────────────────────────────
        data_key, manifest_key = _build_s3_keys(
            raw_prefix=s.s3_raw_prefix,
            ingestion_date=ingestion_date,
        )

        # ── 5. Build manifest ──────────────────────────────────────────────
        manifest = build_manifest(
            local_file=csv_path,
            s3_key=data_key,
            s3_manifest_key=manifest_key,
            row_count=row_count,
            column_count=column_count,
            validation_result=result,
            ingestion_timestamp=ts,
        )
        log.info(
            "pipeline.manifest.built",
            rows=manifest.row_count,
            size_bytes=manifest.file_size_bytes,
            validation_passed=manifest.validation_passed,
        )

        # ── 6. Upload to S3 (skipped in dry-run mode) ─────────────────────
        if dry_run:
            log.info(
                "pipeline.dry_run.upload_skipped",
                data_key=data_key,
                manifest_key=manifest_key,
            )
        else:
            upload_file(
                local_path=csv_path,
                bucket=s.s3_bucket_name,
                s3_key=data_key,
                region=s.aws_region,
            )
            upload_text(
                content=manifest.to_json(),
                bucket=s.s3_bucket_name,
                s3_key=manifest_key,
                region=s.aws_region,
            )
            log.info(
                "pipeline.upload.complete",
                data_uri=f"s3://{s.s3_bucket_name}/{data_key}",
                manifest_uri=f"s3://{s.s3_bucket_name}/{manifest_key}",
            )

    finally:
        if _tmp is not None:
            _tmp.cleanup()

    log.info("pipeline.complete", validation_passed=manifest.validation_passed)
    return manifest


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m ingestion.pipeline",
        description="Ingest the Zomato delivery dataset into the S3 raw zone.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and build the manifest without uploading to S3.",
    )
    parser.add_argument(
        "--local-file",
        type=Path,
        metavar="PATH",
        help="Use a local CSV file instead of downloading from Kaggle.",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = _parse_args()
    result_manifest = run(local_file=args.local_file, dry_run=args.dry_run)
    print(result_manifest.to_json())
    sys.exit(0 if result_manifest.validation_passed else 1)
