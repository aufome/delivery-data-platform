# =============================================================================
# Lambda — Ingestion Trigger
# =============================================================================
# This function receives S3 event notifications when a new file lands in the
# raw zone and triggers the ingestion pipeline.
#
# Phase 3: stub handler — logs the S3 event and returns 200.
# Phase 7: wired to the full pipeline via Airflow or direct invocation.
# =============================================================================

# Package the Lambda handler into a zip archive.
# Terraform regenerates the zip whenever the source file changes.
data "archive_file" "ingestion_handler" {
  type        = "zip"
  source_file = local.lambda_handler_source
  output_path = local.lambda_archive_output
}

resource "aws_lambda_function" "ingestion_trigger" {
  function_name = "${local.name_prefix}-ingestion-trigger"
  description   = "Receives S3 raw-zone events and triggers the ingestion pipeline."

  filename         = data.archive_file.ingestion_handler.output_path
  source_code_hash = data.archive_file.ingestion_handler.output_base64sha256

  runtime = "python3.12"
  handler = "lambda_handler.handler"

  role        = aws_iam_role.lambda_execution.arn
  timeout     = var.lambda_timeout_seconds
  memory_size = var.lambda_memory_mb

  environment {
    variables = {
      ENVIRONMENT      = var.environment
      DATA_LAKE_BUCKET = aws_s3_bucket.data_lake.id
    }
  }

  # Structured logging — emit JSON to CloudWatch so logs can be queried.
  logging_config {
    log_format = "JSON"
    log_group  = "/aws/lambda/${local.name_prefix}-ingestion-trigger"
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic_execution,
    aws_iam_role_policy_attachment.lambda_data_lake,
  ]
}

# =============================================================================
# S3 Event Notification → Lambda
# =============================================================================
# Fires whenever a new object is created directly under raw/delivery_orders/.
# Prefix filter avoids double-firing on manifest.json uploads.
#
# Note: The notification is defined here but the Lambda S3 trigger is
# intentionally left inactive until Phase 7 (Airflow orchestration).
# To disable, comment out this resource and the permission below.
# =============================================================================

resource "aws_lambda_permission" "allow_s3_invoke" {
  statement_id  = "AllowS3Invoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ingestion_trigger.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.data_lake.arn
}

resource "aws_s3_bucket_notification" "raw_zone_trigger" {
  bucket = aws_s3_bucket.data_lake.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.ingestion_trigger.arn
    events              = ["s3:ObjectCreated:*"]

    # Trigger only on new CSV files in the raw delivery_orders zone.
    filter_prefix = "raw/delivery_orders/"
    filter_suffix = ".csv"
  }

  depends_on = [aws_lambda_permission.allow_s3_invoke]
}
