"""
Lambda ingestion trigger — Phase 3 stub.

This handler receives S3 event notifications when a new object lands in
the raw zone of the data lake. It logs the event and returns a success
response.

In Phase 7 (Airflow orchestration), this stub will be replaced or extended
to trigger the full ingestion pipeline — either by starting an Airflow DAG
run or by calling the ingestion.pipeline module directly.

The function is deployed by Terraform using a zip archive of this file.
It does not depend on any third-party packages so no Lambda layer is needed
at this stage.
"""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event: Any, context: object) -> dict[str, Any]:
    """
    Lambda entry point.

    Args:
        event: S3 event payload from the bucket notification.
        context: Lambda runtime context (not used at this stage).

    Returns:
        A dict with statusCode 200 and the number of processed S3 records.
    """
    logger.info(
        "Ingestion trigger received",
        extra={"event_summary": json.dumps(event)[:500]},
    )

    records: list[Any] = event.get("Records", [])
    logger.info("Processing %d S3 event record(s)", len(records))

    for record in records:
        s3 = record.get("s3", {})
        bucket = s3.get("bucket", {}).get("name", "unknown")
        key = s3.get("object", {}).get("key", "unknown")
        size = s3.get("object", {}).get("size", -1)
        logger.info(
            "New S3 object detected",
            extra={"bucket": bucket, "key": key, "size_bytes": size},
        )

    return {
        "statusCode": 200,
        "body": json.dumps({"processed_records": len(records)}),
    }
