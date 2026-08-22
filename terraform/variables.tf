# ── Project identity ──────────────────────────────────────────────────────────

variable "project_name" {
  description = "Short project identifier used as a prefix in all resource names."
  type        = string
  default     = "ddp"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,20}$", var.project_name))
    error_message = "project_name must be lowercase alphanumeric with hyphens, 2-21 characters."
  }
}

variable "environment" {
  description = "Deployment environment. Controls naming and may influence capacity settings."
  type        = string

  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "environment must be 'dev' or 'prod'."
  }
}

# ── AWS ───────────────────────────────────────────────────────────────────────

variable "aws_region" {
  description = "AWS region for all resources."
  type        = string
  default     = "eu-central-1"
}

variable "aws_profile" {
  description = "Named AWS CLI profile. Leave empty to use the default credential chain."
  type        = string
  default     = ""
}

# ── S3 ────────────────────────────────────────────────────────────────────────

variable "data_lake_bucket_name" {
  description = <<-EOT
    Explicit S3 bucket name for the data lake.
    If empty, defaults to "<project_name>-<environment>-data-lake".
    S3 bucket names must be globally unique — set this if the default name is taken.
  EOT
  type        = string
  default     = ""
}

variable "athena_results_bucket_name" {
  description = <<-EOT
    Explicit S3 bucket name for Athena query results.
    If empty, defaults to "<project_name>-<environment>-athena-results".
  EOT
  type        = string
  default     = ""
}

# ── Lambda ────────────────────────────────────────────────────────────────────

variable "lambda_memory_mb" {
  description = "Memory allocated to the ingestion trigger Lambda function (MB)."
  type        = number
  default     = 512
}

variable "lambda_timeout_seconds" {
  description = "Maximum execution time for the ingestion trigger Lambda (seconds)."
  type        = number
  default     = 900 # 15 minutes — Lambda maximum

  validation {
    condition     = var.lambda_timeout_seconds <= 900
    error_message = "Lambda timeout cannot exceed 900 seconds (15 minutes)."
  }
}
