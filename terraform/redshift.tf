# ==============================================================================
# REDSHIFT SERVERLESS CONFIGURATION
# ==============================================================================

resource "aws_iam_role" "redshift_spectrum_role" {
  name = "${var.project_name}-redshift-spectrum-${var.environment}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Action = "sts:AssumeRole",
        Effect = "Allow",
        Principal = {
          Service = "redshift.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Environment = var.environment
    Project     = var.project_name
  }
}

# Allow Redshift to read from the data lake bucket
resource "aws_iam_role_policy" "redshift_s3_read" {
  name = "${var.project_name}-redshift-s3-read"
  role = aws_iam_role.redshift_spectrum_role.id

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ],
        Resource = [
          aws_s3_bucket.data_lake.arn,
          "${aws_s3_bucket.data_lake.arn}/*"
        ]
      }
    ]
  })
}

# Allow Redshift to use the Glue Data Catalog
resource "aws_iam_role_policy_attachment" "redshift_glue_access" {
  role       = aws_iam_role.redshift_spectrum_role.name
  policy_arn = "arn:aws:iam::aws:policy/AWSGlueConsoleFullAccess"
}

# Serverless Namespace
resource "aws_redshiftserverless_namespace" "this" {
  namespace_name      = "${var.project_name}-ns-${var.environment}"
  admin_username      = "admin"
  admin_user_password = var.redshift_admin_password
  iam_roles           = [aws_iam_role.redshift_spectrum_role.arn]

  tags = {
    Environment = var.environment
    Project     = var.project_name
  }
}

# Serverless Workgroup
resource "aws_redshiftserverless_workgroup" "this" {
  namespace_name = aws_redshiftserverless_namespace.this.namespace_name
  workgroup_name = "${var.project_name}-wg-${var.environment}"
  base_capacity  = 8 # Minimum RPU (Redshift Processing Units) to keep costs low

  # Note: Subnet IDs and Security Group IDs would be specified here in a real VPC environment
  # For demo purposes, AWS will place this in the default VPC if not specified.
  
  tags = {
    Environment = var.environment
    Project     = var.project_name
  }
}

# We need to run a SQL command to create the external schema in Redshift,
# but Terraform doesn't natively execute SQL inside Redshift Serverless without a custom provider or script.
# In a real environment, this is usually applied via dbt `on-run-start` hooks or Flyway.
