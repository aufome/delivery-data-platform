"""
Ingestion manifest — records metadata about a completed ingestion run.

The manifest is written as a JSON file alongside the raw data file in S3
so that downstream jobs can inspect ingestion metadata without re-reading
the CSV.

It serves as the primary audit trail for the ingestion process and as
the source of truth for data lineage (what was ingested, when, from where,
and in what state).
"""

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from validation.result import ValidationResult
from validation.schema import SCHEMA_VERSION


def compute_md5(path: Path, chunk_size: int = 8192) -> str:
    """Return the MD5 hex digest of a file, read in chunks."""
    h = hashlib.md5()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class IngestionManifest:
    """
    Metadata produced by a single ingestion run.

    All fields are plain Python types so the manifest can be trivially
    serialised to JSON and stored in S3 or a metadata table.
    """

    source_name: str
    source_file: str
    ingestion_timestamp: str  # ISO-8601, UTC
    ingestion_date: str  # YYYY-MM-DD, used as the S3 partition key
    row_count: int
    column_count: int
    file_size_bytes: int
    md5_checksum: str
    schema_version: str
    s3_key: str
    s3_manifest_key: str
    validation_passed: bool
    validation_error_count: int
    validation_warning_count: int
    validation_violations: list[dict[str, str | None]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


def build_manifest(
    *,
    local_file: Path,
    s3_key: str,
    s3_manifest_key: str,
    row_count: int,
    column_count: int,
    validation_result: ValidationResult,
    source_name: str = "zomato-delivery-operations-analytics-dataset",
    ingestion_timestamp: datetime | None = None,
) -> IngestionManifest:
    """
    Build an ``IngestionManifest`` from ingestion run metadata.

    Args:
        local_file: Path to the raw file on disk (used for size + checksum).
        s3_key: The S3 key where the raw data file will be stored.
        s3_manifest_key: The S3 key where this manifest will be stored.
        row_count: Number of data rows (excluding the header).
        column_count: Number of columns.
        validation_result: Outcome of schema and rule validation.
        source_name: Human-readable source dataset identifier.
        ingestion_timestamp: Override the current UTC time (useful in tests).

    Returns:
        A fully populated ``IngestionManifest``.
    """
    ts = ingestion_timestamp or datetime.now(UTC)

    return IngestionManifest(
        source_name=source_name,
        source_file=local_file.name,
        ingestion_timestamp=ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        ingestion_date=ts.strftime("%Y-%m-%d"),
        row_count=row_count,
        column_count=column_count,
        file_size_bytes=local_file.stat().st_size,
        md5_checksum=compute_md5(local_file),
        schema_version=SCHEMA_VERSION,
        s3_key=s3_key,
        s3_manifest_key=s3_manifest_key,
        validation_passed=validation_result.passed,
        validation_error_count=len(validation_result.errors),
        validation_warning_count=len(validation_result.warnings),
        validation_violations=[v.as_dict() for v in validation_result.violations],
    )
