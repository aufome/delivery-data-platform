"""
Data processing pipeline — Phase 4 entry point.

Reads raw CSV data from the S3 `raw` zone, applies cleaning and feature
engineering transformations, and writes the standardized data as Parquet
to the S3 `processed` zone.

Usage
-----
    # Process today's data from S3
    uv run python -m processing.pipeline --ingestion-date 2024-01-15

    # Process a local file (dry-run, no S3 upload)
    uv run python -m processing.pipeline --local-file /path/to/delivery_data.csv --dry-run
"""

import argparse
import sys
import tempfile
from pathlib import Path

import pandas as pd
import structlog

from config.settings import get_settings
from processing.cleaner import process_dataframe
from processing.s3_client import download_file, upload_file

log = structlog.get_logger(__name__)


def run(
    *,
    ingestion_date: str | None = None,
    local_file: Path | None = None,
    dry_run: bool = False,
) -> None:
    """
    Execute the data processing pipeline.
    """
    s = get_settings()

    if not local_file and not ingestion_date:
        raise ValueError("Must provide either --local-file or --ingestion-date.")

    log.info(
        "processing.start",
        environment=s.environment,
        ingestion_date=ingestion_date,
        dry_run=dry_run,
    )

    _tmp: tempfile.TemporaryDirectory[str] | None = None

    try:
        # ── 1. Acquire the raw file ───────────────────────────────────────
        if local_file is not None:
            log.info("processing.using_local_file", path=str(local_file))
            raw_csv_path = local_file
        else:
            _tmp = tempfile.TemporaryDirectory(prefix="ddp_process_")
            raw_csv_path = Path(_tmp.name) / "raw_delivery_data.csv"

            raw_key = (
                f"{s.s3_raw_path('delivery_orders')}/source=zomato/"
                f"ingestion_date={ingestion_date}/delivery_data.csv"
            )

            download_file(
                bucket=s.s3_bucket_name,
                s3_key=raw_key,
                local_path=raw_csv_path,
                region=s.aws_region,
            )

        # ── 2. Load and process DataFrame ─────────────────────────────────
        log.info("processing.csv.reading", path=str(raw_csv_path))
        df = pd.read_csv(raw_csv_path, low_memory=False)

        log.info("processing.transform.start", input_rows=len(df), input_cols=len(df.columns))
        processed_df = process_dataframe(df)
        log.info("processing.transform.complete", output_cols=len(processed_df.columns))

        # ── 3. Save as Parquet ─────────────────────────────────────────────
        # If we didn't create a temp dir for downloading, we create one for uploading
        if _tmp is None:
            _tmp = tempfile.TemporaryDirectory(prefix="ddp_process_")

        processed_parquet_path = Path(_tmp.name) / "delivery_data.parquet"

        log.info("processing.parquet.writing", path=str(processed_parquet_path))
        # Ensure fastparquet or pyarrow is available
        processed_df.to_parquet(processed_parquet_path, index=False, engine="pyarrow")

        # ── 4. Upload to Processed Zone (skipped in dry-run) ───────────────
        if dry_run:
            log.info("processing.dry_run.upload_skipped")
        else:
            # Reconstruct the date if local file was provided without ingestion_date
            # Defaulting to a placeholder for local ad-hoc runs
            target_date = ingestion_date or "local_dev"
            processed_key = (
                f"{s.s3_processed_path('delivery_orders')}/source=zomato/"
                f"ingestion_date={target_date}/delivery_data.parquet"
            )

            upload_file(
                local_path=processed_parquet_path,
                bucket=s.s3_bucket_name,
                s3_key=processed_key,
                region=s.aws_region,
            )
            log.info(
                "processing.upload.complete",
                processed_uri=f"s3://{s.s3_bucket_name}/{processed_key}",
            )

    finally:
        if _tmp is not None:
            _tmp.cleanup()

    log.info("processing.complete")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m processing.pipeline",
        description="Process raw delivery data and write to the processed zone as Parquet.",
    )
    parser.add_argument(
        "--ingestion-date",
        type=str,
        help="The ingestion date to process (YYYY-MM-DD). Used to construct S3 paths.",
    )
    parser.add_argument(
        "--local-file",
        type=Path,
        metavar="PATH",
        help="Use a local CSV file instead of downloading from S3.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Process the data but skip the S3 Parquet upload.",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = _parse_args()
    try:
        run(
            ingestion_date=args.ingestion_date,
            local_file=args.local_file,
            dry_run=args.dry_run,
        )
    except Exception as e:
        log.error("processing.failed", error=str(e))
        sys.exit(1)
