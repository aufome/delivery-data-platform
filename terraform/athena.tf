# =============================================================================
# Athena Workgroup
# =============================================================================
# All Athena queries must run in this workgroup. The workgroup enforces that
# results are written to the designated results bucket and sets cost controls.
# =============================================================================

resource "aws_athena_workgroup" "main" {
  name        = local.athena_workgroup
  description = "Delivery Data Platform — ${var.environment} workgroup."

  configuration {
    enforce_workgroup_configuration    = true
    publish_cloudwatch_metrics_enabled = true

    result_configuration {
      output_location = "s3://${aws_s3_bucket.athena_results.id}/query-results/"

      encryption_configuration {
        encryption_option = "SSE_S3"
      }
    }

    # Fail queries that would scan more than 1 GB of data (cost guardrail).
    # Increase this for production analytical queries.
    bytes_scanned_cutoff_per_query = 1073741824 # 1 GB
  }
}

# =============================================================================
# Glue Data Catalog — Raw Zone Database
# =============================================================================

resource "aws_glue_catalog_database" "raw" {
  name        = local.glue_database_raw
  description = "Glue database for the raw data lake zone. Tables map to S3 CSV files."
}

# =============================================================================
# Glue Catalog Table — delivery_orders (raw)
# =============================================================================
# External table over:
#   s3://<data-lake-bucket>/raw/delivery_orders/
#
# Partition keys mirror the S3 Hive-style path:
#   source=zomato / ingestion_date=YYYY-MM-DD
#
# All columns are STRING to preserve the original raw representation.
# Type conversion happens downstream in dbt (Phase 6).
#
# Column names use snake_case because Hive/Athena lowercases identifiers.
# The CSV SerDe maps columns by position (not name) so column order must
# match the header order in the source CSV file.
# =============================================================================

resource "aws_glue_catalog_table" "delivery_orders" {
  name          = "delivery_orders"
  database_name = aws_glue_catalog_database.raw.name
  description   = "Raw delivery orders from the Zomato dataset, partitioned by ingestion date."

  table_type = "EXTERNAL_TABLE"

  parameters = {
    "classification"         = "csv"
    "has_encrypted_data"     = "false"
    "skip.header.line.count" = "1"
    "EXTERNAL"               = "TRUE"
  }

  storage_descriptor {
    location      = "s3://${aws_s3_bucket.data_lake.id}/raw/delivery_orders/"
    input_format  = "org.apache.hadoop.mapred.TextInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat"

    ser_de_info {
      name                  = "OpenCSVSerDe"
      serialization_library = "org.apache.hadoop.hive.serde2.OpenCSVSerde"

      parameters = {
        "separatorChar" = ","
        "quoteChar"     = "\""
        "escapeChar"    = "\\"
      }
    }

    # Column order must match the CSV header exactly.
    # Source: validation/schema.py EXPECTED_COLUMNS
    columns {
      name    = "id"
      type    = "string"
      comment = "Unique delivery record identifier"
    }
    columns {
      name    = "delivery_person_id"
      type    = "string"
      comment = "Delivery person identifier"
    }
    columns {
      name    = "delivery_person_age"
      type    = "string"
      comment = "Age of the delivery person (raw string)"
    }
    columns {
      name    = "delivery_person_ratings"
      type    = "string"
      comment = "Delivery person rating (raw string)"
    }
    columns {
      name    = "restaurant_latitude"
      type    = "string"
      comment = "Restaurant latitude (raw string)"
    }
    columns {
      name    = "restaurant_longitude"
      type    = "string"
      comment = "Restaurant longitude (raw string)"
    }
    columns {
      name    = "delivery_location_latitude"
      type    = "string"
      comment = "Delivery destination latitude (raw string)"
    }
    columns {
      name    = "delivery_location_longitude"
      type    = "string"
      comment = "Delivery destination longitude (raw string)"
    }
    columns {
      name    = "order_date"
      type    = "string"
      comment = "Order date (DD-MM-YYYY format in source)"
    }
    columns {
      name    = "time_orderd"
      type    = "string"
      comment = "Time order was placed (HH:MM)"
    }
    columns {
      name    = "time_order_picked"
      type    = "string"
      comment = "Time order was picked up (HH:MM)"
    }
    columns {
      name    = "weather_conditions"
      type    = "string"
      comment = "Categorical weather condition at time of delivery"
    }
    columns {
      name    = "road_traffic_density"
      type    = "string"
      comment = "Categorical traffic density at time of delivery"
    }
    columns {
      name    = "vehicle_condition"
      type    = "string"
      comment = "Vehicle condition score (raw string)"
    }
    columns {
      name    = "type_of_order"
      type    = "string"
      comment = "Order category (Snack, Meal, Drinks, Buffet)"
    }
    columns {
      name    = "type_of_vehicle"
      type    = "string"
      comment = "Vehicle type used for delivery"
    }
    columns {
      name    = "multiple_deliveries"
      type    = "string"
      comment = "Number of simultaneous deliveries (raw string)"
    }
    columns {
      name    = "festival"
      type    = "string"
      comment = "Festival indicator (Yes / No)"
    }
    columns {
      name    = "city"
      type    = "string"
      comment = "City category (Metropolitian / Urban / Semi-Urban)"
    }
    columns {
      name    = "time_taken_min"
      type    = "string"
      comment = "Delivery duration in minutes. Raw format: '(24) ' — cleaned in Phase 4."
    }
  }

  partition_keys {
    name    = "source"
    type    = "string"
    comment = "Source system identifier (always 'zomato' for this dataset)"
  }

  partition_keys {
    name    = "ingestion_date"
    type    = "string"
    comment = "Date the file was ingested (YYYY-MM-DD)"
  }
}
