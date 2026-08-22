# =============================================================================
# S3 — Data Lake Bucket
# =============================================================================
# Central data lake. Zone prefixes (raw/validated/processed/analytics) are
# managed by application code — not enforced by separate S3 buckets.
# This keeps the architecture simple and avoids cross-bucket IAM complexity.
# =============================================================================

resource "aws_s3_bucket" "data_lake" {
  bucket = local.data_lake_bucket_name

  # Prevent accidental deletion of the bucket and its contents.
  # Set to false when running terraform destroy intentionally.
  lifecycle {
    prevent_destroy = false
  }
}

resource "aws_s3_bucket_versioning" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id

  versioning_configuration {
    # Versioning preserves overwritten or deleted objects.
    # Required for raw zone immutability (guide section 2.4).
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id

  rule {
    id     = "abort-incomplete-multipart-uploads"
    status = "Enabled"

    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }

  rule {
    id     = "expire-old-versions"
    status = "Enabled"

    filter {
      prefix = "raw/"
    }

    # Keep non-current versions for 90 days then delete.
    # The current version (immutable raw file) is never touched by this rule.
    noncurrent_version_expiration {
      noncurrent_days = 90
    }
  }
}

# =============================================================================
# S3 — Athena Query Results Bucket
# =============================================================================
# Athena writes query results here. Separate bucket keeps data lake clean.
# =============================================================================

resource "aws_s3_bucket" "athena_results" {
  bucket = local.athena_results_bucket_name
}

resource "aws_s3_bucket_server_side_encryption_configuration" "athena_results" {
  bucket = aws_s3_bucket.athena_results.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "athena_results" {
  bucket = aws_s3_bucket.athena_results.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "athena_results" {
  bucket = aws_s3_bucket.athena_results.id

  rule {
    id     = "expire-query-results"
    status = "Enabled"

    filter {}

    # Athena query results are transient — expire after 30 days.
    expiration {
      days = 30
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}
