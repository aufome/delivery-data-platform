"""
S3 utilities for the processing phase.

Handles downloading raw files and uploading processed Parquet/CSV files.
Reuses the S3Client typing from mypy_boto3_s3.
"""

from pathlib import Path

import boto3
import structlog
from boto3.exceptions import S3UploadFailedError
from botocore.exceptions import BotoCoreError, ClientError
from mypy_boto3_s3 import S3Client

log = structlog.get_logger(__name__)


def _s3_client(region: str) -> S3Client:
    return boto3.client("s3", region_name=region)


def download_file(
    bucket: str,
    s3_key: str,
    local_path: Path,
    *,
    region: str,
) -> None:
    """
    Download a file from S3 to a local path.

    Raises:
        RuntimeError: If the download fails.
    """
    log.info(
        "s3.download_file.start",
        bucket=bucket,
        key=s3_key,
        local_path=str(local_path),
    )

    try:
        _s3_client(region).download_file(
            Bucket=bucket,
            Key=s3_key,
            Filename=str(local_path),
        )
    except (BotoCoreError, ClientError) as exc:
        log.error("s3.download_file.failed", bucket=bucket, key=s3_key, error=str(exc))
        raise RuntimeError(
            f"Failed to download s3://{bucket}/{s3_key} to '{local_path}': {exc}"
        ) from exc

    log.info(
        "s3.download_file.complete",
        bucket=bucket,
        key=s3_key,
        size_bytes=local_path.stat().st_size,
    )


def upload_file(
    local_path: Path,
    bucket: str,
    s3_key: str,
    *,
    region: str,
    extra_args: dict[str, str] | None = None,
) -> None:
    """
    Upload a local file to S3.

    Raises:
        FileNotFoundError: If `local_path` does not exist.
        RuntimeError: If the upload fails.
    """
    if not local_path.exists():
        raise FileNotFoundError(f"Cannot upload: '{local_path}' does not exist.")

    log.info(
        "s3.upload_file.start",
        local_path=str(local_path),
        bucket=bucket,
        key=s3_key,
        size_bytes=local_path.stat().st_size,
    )

    try:
        _s3_client(region).upload_file(
            Filename=str(local_path),
            Bucket=bucket,
            Key=s3_key,
            ExtraArgs=extra_args or {},
        )
    except (BotoCoreError, ClientError, S3UploadFailedError) as exc:
        log.error("s3.upload_file.failed", bucket=bucket, key=s3_key, error=str(exc))
        raise RuntimeError(
            f"Failed to upload '{local_path}' to s3://{bucket}/{s3_key}: {exc}"
        ) from exc

    log.info("s3.upload_file.complete", bucket=bucket, key=s3_key)
