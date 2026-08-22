"""
Enrichment pipeline — Phase 5 entry point.

Reads processed delivery data, fetches missing historical weather data,
joins them, and outputs the enriched dataset as Parquet.

Usage
-----
    uv run python -m enrichment.pipeline --ingestion-date 2024-01-15
    uv run python -m enrichment.pipeline --local-file /path/to/processed.parquet --dry-run
"""

import argparse
import sys
import tempfile
from pathlib import Path

import pandas as pd
import structlog

from config.settings import get_settings
from enrichment.enricher import enrich_delivery_data, parse_weather_json
from enrichment.weather_ingestion import ingest_weather_for_orders
from processing.s3_client import download_file, upload_file

log = structlog.get_logger(__name__)


def run(
    *,
    ingestion_date: str | None = None,
    local_file: Path | None = None,
    dry_run: bool = False,
) -> None:
    s = get_settings()

    if not local_file and not ingestion_date:
        raise ValueError("Must provide either --local-file or --ingestion-date.")

    log.info("enrichment.start", ingestion_date=ingestion_date, dry_run=dry_run)
    _tmp: tempfile.TemporaryDirectory[str] | None = None

    try:
        # 1. Acquire Processed Parquet
        if local_file is not None:
            processed_path = local_file
        else:
            _tmp = tempfile.TemporaryDirectory(prefix="ddp_enrich_")
            processed_path = Path(_tmp.name) / "processed_data.parquet"
            s3_key = f"{s.s3_processed_path('delivery_orders')}/source=zomato/ingestion_date={ingestion_date}/delivery_data.parquet"
            download_file(s.s3_bucket_name, s3_key, processed_path, region=s.aws_region)

        log.info("enrichment.reading_processed", path=str(processed_path))
        df = pd.read_parquet(processed_path)

        # 2. Ingest Weather
        target_date = ingestion_date or "local_dev"
        weather_json_path = ingest_weather_for_orders(df, target_date, dry_run=dry_run)

        if not weather_json_path:
            log.warning("enrichment.no_weather_fetched")
            enriched_df = df
        else:
            # 3. Parse and Enrich
            log.info("enrichment.parsing_weather", path=str(weather_json_path))
            weather_df = parse_weather_json(weather_json_path)

            log.info("enrichment.joining")
            enriched_df = enrich_delivery_data(df, weather_df)

        # 4. Save Enriched Data
        if _tmp is None:
            _tmp = tempfile.TemporaryDirectory(prefix="ddp_enrich_")

        enriched_path = Path(_tmp.name) / "enriched_data.parquet"
        enriched_df.to_parquet(enriched_path, index=False, engine="pyarrow")

        log.info("enrichment.saved_locally", path=str(enriched_path), rows=len(enriched_df))

        # 5. Upload to S3
        if dry_run:
            log.info("enrichment.dry_run.upload_skipped")
        else:
            enriched_key = f"{s.s3_processed_path('enriched_delivery_orders')}/source=zomato/ingestion_date={target_date}/delivery_data.parquet"
            upload_file(enriched_path, s.s3_bucket_name, enriched_key, region=s.aws_region)
            log.info("enrichment.upload.complete", s3_key=enriched_key)

    finally:
        if _tmp is not None:
            _tmp.cleanup()

    log.info("enrichment.complete")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enrich processed data with weather.")
    parser.add_argument("--ingestion-date", type=str)
    parser.add_argument("--local-file", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = _parse_args()
    try:
        run(ingestion_date=args.ingestion_date, local_file=args.local_file, dry_run=args.dry_run)
    except Exception as e:
        log.error("enrichment.failed", error=str(e))
        sys.exit(1)
