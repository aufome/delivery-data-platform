"""
Lambda ingestion trigger.

This handler receives S3 event notifications when a new object lands in
the raw zone of the data lake. It triggers the Airflow pipeline via its REST API.

The function is deployed by Terraform using a zip archive of this file.
"""

import base64
import json
import logging
import os
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event: Any, context: Any) -> dict[str, Any]:
    """
    AWS Lambda handler triggered by S3 ObjectCreated events.
    """
    airflow_url = os.environ.get("AIRFLOW_API_URL", "http://localhost:8080/api/v1/dags/delivery_data_pipeline/dagRuns")
    airflow_user = os.environ.get("AIRFLOW_USER", "admin")
    airflow_pass = os.environ.get("AIRFLOW_PASS", "admin")

    records = event.get("Records", [])
    logger.info("ingestion.lambda.triggered", extra={"records_count": len(records)})

    responses = []

    for record in records:
        bucket = record["s3"]["bucket"]["name"]
        key = record["s3"]["object"]["key"]

        logger.info("ingestion.lambda.processing_record", extra={"bucket": bucket, "key": key})

        payload = json.dumps({"conf": {"s3_bucket": bucket, "s3_key": key}}).encode("utf-8")

        auth_str = f"{airflow_user}:{airflow_pass}"
        b64_auth = base64.b64encode(auth_str.encode("utf-8")).decode("ascii")

        req = urllib.request.Request(
            airflow_url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Basic {b64_auth}"
            }
        )

        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                resp_body = response.read().decode("utf-8")
                logger.info("ingestion.lambda.airflow_triggered", extra={"status": response.status, "response": resp_body})
                responses.append({"key": key, "status": response.status})
        except Exception as e:
            logger.error("ingestion.lambda.airflow_trigger_failed", extra={"error": str(e), "key": key})

    return {
        "statusCode": 200,
        "body": json.dumps({"message": "Processed S3 events", "results": responses})
    }
