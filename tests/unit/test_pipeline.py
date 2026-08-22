"""
Unit tests for ingestion.pipeline.

Tests cover dry-run mode, local-file mode, S3 key construction, and
a full run against a mocked S3 bucket. No Kaggle network calls are made.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import boto3
import pandas as pd
import pytest
from moto import mock_aws

from ingestion.pipeline import _build_s3_keys, run
from validation.schema import EXPECTED_COLUMNS

BUCKET = "test-bucket"
REGION = "eu-central-1"
FIXED_TS = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)


# ── Fixtures ──────────────────────────────────────────────────────────────────


def _make_valid_csv(path: Path) -> None:
    """Write a minimal valid delivery CSV to ``path``."""
    rows = 10
    df = pd.DataFrame(
        {
            "ID": [f"RES{i:05d}DEL01" for i in range(rows)],
            "Delivery_person_ID": [f"DEL{i:05d}" for i in range(rows)],
            "Delivery_person_Age": ["25"] * rows,
            "Delivery_person_Ratings": ["4.5"] * rows,
            "Restaurant_latitude": [12.9716] * rows,
            "Restaurant_longitude": [77.5946] * rows,
            "Delivery_location_latitude": [12.9816] * rows,
            "Delivery_location_longitude": [77.6046] * rows,
            "Order_Date": ["15-03-2022"] * rows,
            "Time_Orderd": ["10:30"] * rows,
            "Time_Order_picked": ["10:45"] * rows,
            "Weather_conditions": ["Sunny"] * rows,
            "Road_traffic_density": ["Medium"] * rows,
            "Vehicle_condition": ["0"] * rows,
            "Type_of_order": ["Meal"] * rows,
            "Type_of_vehicle": ["motorcycle"] * rows,
            "multiple_deliveries": ["0"] * rows,
            "Festival": ["No"] * rows,
            "City": ["Urban"] * rows,
            "Time_taken (min)": ["(25) "] * rows,
        }
    )
    df.to_csv(path, index=False)


@pytest.fixture()
def valid_csv(tmp_path: Path) -> Path:
    csv_path = tmp_path / "delivery_data.csv"
    _make_valid_csv(csv_path)
    return csv_path


def _setup_s3_bucket() -> None:
    boto3.client("s3", region_name=REGION).create_bucket(
        Bucket=BUCKET,
        CreateBucketConfiguration={"LocationConstraint": REGION},
    )


# ── _build_s3_keys ────────────────────────────────────────────────────────────


class TestBuildS3Keys:
    def test_data_key_contains_ingestion_date(self) -> None:
        data_key, _ = _build_s3_keys("raw", "2024-01-15")
        assert "ingestion_date=2024-01-15" in data_key

    def test_data_key_ends_with_csv(self) -> None:
        data_key, _ = _build_s3_keys("raw", "2024-01-15")
        assert data_key.endswith("delivery_data.csv")

    def test_manifest_key_ends_with_json(self) -> None:
        _, manifest_key = _build_s3_keys("raw", "2024-01-15")
        assert manifest_key.endswith("manifest.json")

    def test_keys_share_same_prefix(self) -> None:
        data_key, manifest_key = _build_s3_keys("raw", "2024-01-15")
        assert data_key.rsplit("/", 1)[0] == manifest_key.rsplit("/", 1)[0]

    def test_source_partition_present(self) -> None:
        data_key, _ = _build_s3_keys("raw", "2024-01-15")
        assert "source=zomato" in data_key


# ── run — dry-run mode ────────────────────────────────────────────────────────


class TestRunDryRun:
    def test_returns_manifest(self, settings_env: None, valid_csv: Path) -> None:
        from ingestion.manifest import IngestionManifest

        manifest = run(local_file=valid_csv, dry_run=True, ingestion_timestamp=FIXED_TS)
        assert isinstance(manifest, IngestionManifest)

    def test_validation_passed_for_valid_csv(self, settings_env: None, valid_csv: Path) -> None:
        manifest = run(local_file=valid_csv, dry_run=True, ingestion_timestamp=FIXED_TS)
        assert manifest.validation_passed is True

    def test_row_count_matches_csv(self, settings_env: None, valid_csv: Path) -> None:
        manifest = run(local_file=valid_csv, dry_run=True, ingestion_timestamp=FIXED_TS)
        assert manifest.row_count == 10

    def test_column_count_matches_csv(self, settings_env: None, valid_csv: Path) -> None:
        manifest = run(local_file=valid_csv, dry_run=True, ingestion_timestamp=FIXED_TS)
        assert manifest.column_count == len(EXPECTED_COLUMNS)

    def test_ingestion_date_in_s3_key(self, settings_env: None, valid_csv: Path) -> None:
        manifest = run(local_file=valid_csv, dry_run=True, ingestion_timestamp=FIXED_TS)
        assert "2024-01-15" in manifest.s3_key

    def test_manifest_json_is_valid(self, settings_env: None, valid_csv: Path) -> None:
        manifest = run(local_file=valid_csv, dry_run=True, ingestion_timestamp=FIXED_TS)
        parsed = json.loads(manifest.to_json())
        assert parsed["source_name"] == "zomato-delivery-operations-analytics-dataset"


# ── run — full upload to mocked S3 ───────────────────────────────────────────


class TestRunWithS3Upload:
    def test_data_and_manifest_uploaded(
        self, settings_env: None, aws_credentials: None, valid_csv: Path
    ) -> None:
        with mock_aws():
            _setup_s3_bucket()
            manifest = run(
                local_file=valid_csv,
                dry_run=False,
                ingestion_timestamp=FIXED_TS,
            )

            client = boto3.client("s3", region_name=REGION)

            # CSV exists in S3
            resp = client.get_object(Bucket=BUCKET, Key=manifest.s3_key)
            assert resp["ResponseMetadata"]["HTTPStatusCode"] == 200

            # Manifest JSON exists in S3
            resp = client.get_object(Bucket=BUCKET, Key=manifest.s3_manifest_key)
            stored = json.loads(resp["Body"].read())
            assert stored["ingestion_date"] == "2024-01-15"

    def test_s3_manifest_matches_returned_manifest(
        self, settings_env: None, aws_credentials: None, valid_csv: Path
    ) -> None:
        with mock_aws():
            _setup_s3_bucket()
            manifest = run(
                local_file=valid_csv,
                dry_run=False,
                ingestion_timestamp=FIXED_TS,
            )

            client = boto3.client("s3", region_name=REGION)
            resp = client.get_object(Bucket=BUCKET, Key=manifest.s3_manifest_key)
            stored = json.loads(resp["Body"].read())

            assert stored["row_count"] == manifest.row_count
            assert stored["md5_checksum"] == manifest.md5_checksum


# ── run — invalid CSV ─────────────────────────────────────────────────────────


class TestRunWithInvalidCsv:
    def test_invalid_csv_still_produces_manifest(self, settings_env: None, tmp_path: Path) -> None:
        """Validation failures must not prevent the manifest from being built."""
        bad_csv = tmp_path / "bad.csv"
        # Missing most required columns
        bad_csv.write_text("ID,some_other_col\n1,value\n")

        manifest = run(local_file=bad_csv, dry_run=True, ingestion_timestamp=FIXED_TS)
        assert manifest.validation_passed is False
        assert manifest.validation_error_count > 0
