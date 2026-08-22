# ── S3 ────────────────────────────────────────────────────────────────────────

output "data_lake_bucket_name" {
  description = "Name of the S3 data lake bucket."
  value       = aws_s3_bucket.data_lake.id
}

output "data_lake_bucket_arn" {
  description = "ARN of the S3 data lake bucket."
  value       = aws_s3_bucket.data_lake.arn
}

output "athena_results_bucket_name" {
  description = "Name of the S3 bucket used for Athena query results."
  value       = aws_s3_bucket.athena_results.id
}

# ── Lambda ────────────────────────────────────────────────────────────────────

output "lambda_function_name" {
  description = "Name of the ingestion trigger Lambda function."
  value       = aws_lambda_function.ingestion_trigger.function_name
}

output "lambda_function_arn" {
  description = "ARN of the ingestion trigger Lambda function."
  value       = aws_lambda_function.ingestion_trigger.arn
}

output "lambda_role_arn" {
  description = "ARN of the IAM role attached to the Lambda function."
  value       = aws_iam_role.lambda_execution.arn
}

# ── Athena ────────────────────────────────────────────────────────────────────

output "athena_workgroup_name" {
  description = "Name of the Athena workgroup."
  value       = aws_athena_workgroup.main.name
}

output "glue_database_raw" {
  description = "Name of the Glue Data Catalog database for the raw zone."
  value       = aws_glue_catalog_database.raw.name
}

output "glue_table_delivery_orders" {
  description = "Name of the Glue table for raw delivery orders."
  value       = aws_glue_catalog_table.delivery_orders.name
}

# ── Quick-start hints ─────────────────────────────────────────────────────────

output "athena_query_example" {
  description = "Example Athena SQL to inspect the most recent ingestion."
  value       = <<-EOQ
    -- Run in Athena workgroup: ${aws_athena_workgroup.main.name}
    SELECT *
    FROM   "${aws_glue_catalog_database.raw.name}"."${aws_glue_catalog_table.delivery_orders.name}"
    WHERE  ingestion_date = (
               SELECT MAX(ingestion_date)
               FROM   "${aws_glue_catalog_database.raw.name}"."${aws_glue_catalog_table.delivery_orders.name}"
           )
    LIMIT  100;
  EOQ
}
