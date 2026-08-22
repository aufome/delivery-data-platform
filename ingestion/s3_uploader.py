"""
S3 upload utilities for the ingestion pipeline.

Thin wrappers around boto3 that handle the two upload patterns used by
the pipeline:

- ``upload_file``: Upload a local file (the raw CSV).
- ``upload_text``: Upload a string as an S3 object (the manifest JSON).

Credentials are resolved via the standard boto3 credential chain
(environment variables → ``~/.aws/credentials`` → IAM role).
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

    Args:
        local_path: Path to the file on disk.
        bucket: Target S3 bucket name.
        s3_key: Destination object key within the bucket.
        region: AWS region of the bucket.
        extra_args: Optional ``ExtraArgs`` passed to boto3 (e.g. ContentType).

    Raises:
        FileNotFoundError: If ``local_path`` does not exist.
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


def upload_text(
    content: str,
    bucket: str,
    s3_key: str,
    *,
    region: str,
    content_type: str = "application/json",
) -> None:
    """
    Upload a string as an S3 object.

    Used to upload the manifest JSON without writing a temporary file.

    Args:
        content: String content to upload.
        bucket: Target S3 bucket name.
        s3_key: Destination object key.
        region: AWS region of the bucket.
        content_type: MIME type of the content.

    Raises:
        RuntimeError: If the upload fails.
    """
    log.info("s3.put_object.start", bucket=bucket, key=s3_key)

    try:
        _s3_client(region).put_object(
            Bucket=bucket,
            Key=s3_key,
            Body=content.encode("utf-8"),
            ContentType=content_type,
        )
    except (BotoCoreError, ClientError) as exc:
        log.error("s3.put_object.failed", bucket=bucket, key=s3_key, error=str(exc))
        raise RuntimeError(f"Failed to put object at s3://{bucket}/{s3_key}: {exc}") from exc

    log.info("s3.put_object.complete", bucket=bucket, key=s3_key)
