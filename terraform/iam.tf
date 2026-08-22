# =============================================================================
# IAM — Lambda Execution Role
# =============================================================================

data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    sid     = "LambdaAssumeRole"
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda_execution" {
  name               = "${local.name_prefix}-lambda-execution"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

# Attach AWS managed policy for basic Lambda logging to CloudWatch.
resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# =============================================================================
# IAM — Lambda Data Lake Policy (least-privilege)
# =============================================================================
# Lambda may read raw/ and write to validated/ and processed/.
# It must NOT write to raw/ (immutability) or analytics/ (reserved for dbt).
# =============================================================================

data "aws_iam_policy_document" "lambda_data_lake" {
  # Read raw zone (to inspect ingested files).
  statement {
    sid    = "ReadRawZone"
    effect = "Allow"

    actions = [
      "s3:GetObject",
      "s3:GetObjectVersion",
      "s3:ListBucket",
    ]

    resources = [
      aws_s3_bucket.data_lake.arn,
      "${aws_s3_bucket.data_lake.arn}/raw/*",
    ]
  }

  # Write validated and processed zones (downstream of raw).
  statement {
    sid    = "WriteProcessedZones"
    effect = "Allow"

    actions = [
      "s3:PutObject",
      "s3:DeleteObject",
    ]

    resources = [
      "${aws_s3_bucket.data_lake.arn}/validated/*",
      "${aws_s3_bucket.data_lake.arn}/processed/*",
    ]
  }

  # Read and write Athena results bucket.
  statement {
    sid    = "AthenaResults"
    effect = "Allow"

    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:ListBucket",
    ]

    resources = [
      aws_s3_bucket.athena_results.arn,
      "${aws_s3_bucket.athena_results.arn}/*",
    ]
  }

  # Athena and Glue Catalog access (for querying raw zone data).
  statement {
    sid    = "AthenaQuery"
    effect = "Allow"

    actions = [
      "athena:StartQueryExecution",
      "athena:GetQueryExecution",
      "athena:GetQueryResults",
      "athena:StopQueryExecution",
    ]

    resources = [
      aws_athena_workgroup.main.arn,
    ]
  }

  statement {
    sid    = "GlueCatalogRead"
    effect = "Allow"

    actions = [
      "glue:GetDatabase",
      "glue:GetDatabases",
      "glue:GetTable",
      "glue:GetTables",
      "glue:GetPartition",
      "glue:GetPartitions",
      "glue:BatchGetPartition",
    ]

    resources = ["*"]
  }
}

resource "aws_iam_policy" "lambda_data_lake" {
  name        = "${local.name_prefix}-lambda-data-lake"
  description = "Least-privilege data lake access for the ingestion Lambda."
  policy      = data.aws_iam_policy_document.lambda_data_lake.json
}

resource "aws_iam_role_policy_attachment" "lambda_data_lake" {
  role       = aws_iam_role.lambda_execution.name
  policy_arn = aws_iam_policy.lambda_data_lake.arn
}
