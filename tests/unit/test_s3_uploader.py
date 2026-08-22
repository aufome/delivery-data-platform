"""
Unit tests for ingestion.s3_uploader.

Uses moto to mock S3 — no real AWS credentials or network needed.

Each test class opens its own mock_aws() context manager so that bucket
state never leaks between tests. The s3_bucket fixture creates the bucket
inside that context; tests must activate mock_aws themselves if they need
the mock active during the upload call.
"""

import tempfile
from pathlib import Path

import boto3
import pytest
from moto import mock_aws

from ingestion.s3_uploader import upload_file, upload_text

BUCKET = "test-bucket"
REGION = "eu-central-1"


# ── Helpers ───────────────────────────────────────────────────────────────────


def _create_bucket(region: str = REGION, bucket: str = BUCKET) -> None:
    boto3.client("s3", region_name=region).create_bucket(
        Bucket=bucket,
        CreateBucketConfiguration={"LocationConstraint": region},
    )


def _temp_csv() -> Path:
    tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
    tmp.write(b"id,value\n1,hello\n2,world\n")
    tmp.close()
    return Path(tmp.name)


# ── upload_file ───────────────────────────────────────────────────────────────


class TestUploadFile:
    def test_file_exists_in_s3_after_upload(self, aws_credentials: None) -> None:
        csv = _temp_csv()
        key = "raw/delivery_orders/source=zomato/delivery_data.csv"
        try:
            with mock_aws():
                _create_bucket()
                upload_file(csv, BUCKET, key, region=REGION)

                resp = boto3.client("s3", region_name=REGION).get_object(Bucket=BUCKET, Key=key)
                assert resp["Body"].read() == csv.read_bytes()
        finally:
            csv.unlink(missing_ok=True)

    def test_file_content_matches(self, aws_credentials: None) -> None:
        csv = _temp_csv()
        key = "raw/test.csv"
        try:
            with mock_aws():
                _create_bucket()
                upload_file(csv, BUCKET, key, region=REGION)

                resp = boto3.client("s3", region_name=REGION).get_object(Bucket=BUCKET, Key=key)
                assert b"id,value" in resp["Body"].read()
        finally:
            csv.unlink(missing_ok=True)

    def test_upload_file_raises_on_missing_file(self, aws_credentials: None) -> None:
        with mock_aws():
            _create_bucket()
            with pytest.raises(FileNotFoundError, match="does not exist"):
                upload_file(
                    Path("/nonexistent/file.csv"),
                    BUCKET,
                    "some/key.csv",
                    region=REGION,
                )

    def test_upload_file_raises_runtime_error_on_bad_bucket(self, aws_credentials: None) -> None:
        csv = _temp_csv()
        try:
            with mock_aws():
                # No bucket created — upload should fail with RuntimeError.
                with pytest.raises(RuntimeError, match="Failed to upload"):
                    upload_file(csv, "nonexistent-bucket", "key.csv", region=REGION)
        finally:
            csv.unlink(missing_ok=True)


# ── upload_text ───────────────────────────────────────────────────────────────


class TestUploadText:
    def test_text_stored_in_s3(self, aws_credentials: None) -> None:
        key = "raw/delivery_orders/source=zomato/manifest.json"
        content = '{"ingestion_date": "2024-01-15"}'
        with mock_aws():
            _create_bucket()
            upload_text(content, BUCKET, key, region=REGION)

            resp = boto3.client("s3", region_name=REGION).get_object(Bucket=BUCKET, Key=key)
            assert resp["Body"].read().decode() == content

    def test_content_type_header_set(self, aws_credentials: None) -> None:
        key = "raw/manifest.json"
        with mock_aws():
            _create_bucket()
            upload_text("{}", BUCKET, key, region=REGION, content_type="application/json")

            resp = boto3.client("s3", region_name=REGION).head_object(Bucket=BUCKET, Key=key)
            assert resp["ContentType"] == "application/json"

    def test_upload_text_raises_on_bad_bucket(self, aws_credentials: None) -> None:
        with mock_aws():
            with pytest.raises(RuntimeError, match="Failed to put object"):
                upload_text("{}", "nonexistent-bucket", "key.json", region=REGION)
