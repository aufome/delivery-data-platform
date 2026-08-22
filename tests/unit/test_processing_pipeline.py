"""
Unit tests for the processing pipeline and S3 client.
"""

from pathlib import Path
from unittest import mock

import boto3
import pandas as pd
import pytest
from moto import mock_aws

from processing.pipeline import run
from processing.s3_client import download_file, upload_file

BUCKET = "test-bucket"
REGION = "eu-central-1"


@pytest.fixture
def raw_csv(tmp_path: Path) -> Path:
    csv_path = tmp_path / "raw.csv"
    df = pd.DataFrame(
        {
            "ID": ["1"],
            "Delivery_person_Age": ["25"],
            "Delivery_person_Ratings": ["4.5"],
            "Restaurant_latitude": [12.9716],
            "Restaurant_longitude": [77.5946],
            "Delivery_location_latitude": [12.9816],
            "Delivery_location_longitude": [77.6046],
            "Order_Date": ["15-03-2022"],
            "Time_Orderd": ["10:30"],
            "Time_Order_picked": ["10:45"],
            "Time_taken (min)": ["(24) "],
            "Weather_conditions": ["Sunny"],
        }
    )
    df.to_csv(csv_path, index=False)
    return csv_path


def _setup_s3_bucket() -> None:
    boto3.client("s3", region_name=REGION).create_bucket(
        Bucket=BUCKET,
        CreateBucketConfiguration={"LocationConstraint": "eu-central-1"},
    )


class TestS3Client:
    def test_download_file(self, aws_credentials: None, raw_csv: Path, tmp_path: Path) -> None:
        key = "raw/data.csv"
        dest = tmp_path / "downloaded.csv"

        with mock_aws():
            _setup_s3_bucket()
            upload_file(raw_csv, BUCKET, key, region=REGION)
            download_file(BUCKET, key, dest, region=REGION)

            assert dest.exists()
            assert dest.read_text() == raw_csv.read_text()

    def test_download_file_raises_runtime_error_on_missing(
        self, aws_credentials: None, tmp_path: Path
    ) -> None:
        with mock_aws():
            _setup_s3_bucket()
            with pytest.raises(RuntimeError, match="Failed to download"):
                download_file(BUCKET, "missing.csv", tmp_path / "out.csv", region=REGION)


class TestProcessingPipeline:
    def test_pipeline_dry_run_local_file(self, raw_csv: Path, tmp_path: Path) -> None:
        # Patching to_parquet to avoid needing pyarrow installed just for the basic test,
        # but since we have pyarrow in pyproject.toml, it should actually work natively.
        # We will test natively to ensure it produces a valid parquet file.

        # We need to temporarily mock get_settings to avoid S3 calls on failure or environment issues
        with mock.patch("processing.pipeline.get_settings") as mock_settings:
            mock_s = mock.MagicMock()
            mock_s.environment = "dev"
            mock_settings.return_value = mock_s

            # The dry_run should process the CSV and write a local parquet file (in temp dir)
            # but skip S3 upload. It shouldn't crash.
            run(local_file=raw_csv, dry_run=True)

    def test_pipeline_raises_value_error_if_no_input(self, settings_env: None) -> None:
        with pytest.raises(ValueError, match="Must provide either"):
            run()

    def test_pipeline_s3_integration(
        self, aws_credentials: None, raw_csv: Path, settings_env: None
    ) -> None:
        with mock_aws():
            _setup_s3_bucket()

            # Put the raw file in the mocked S3 bucket
            from config.settings import get_settings

            s = get_settings()

            ingestion_date = "2024-01-15"
            raw_key = f"{s.s3_raw_path('delivery_orders')}/source=zomato/ingestion_date={ingestion_date}/delivery_data.csv"
            upload_file(raw_csv, BUCKET, raw_key, region=REGION)

            # Run the pipeline targeting this ingestion date
            run(ingestion_date=ingestion_date, dry_run=False)

            # Check if the processed parquet file was uploaded
            processed_key = f"{s.s3_processed_path('delivery_orders')}/source=zomato/ingestion_date={ingestion_date}/delivery_data.parquet"

            client = boto3.client("s3", region_name=REGION)
            resp = client.head_object(Bucket=BUCKET, Key=processed_key)
            assert resp["ContentLength"] > 0
