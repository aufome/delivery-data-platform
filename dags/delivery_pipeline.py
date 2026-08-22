"""
Apache Airflow DAG for the Delivery Data Platform.

Orchestrates the end-to-end data pipeline:
1. Ingestion (Raw CSV from Kaggle)
2. Processing (Cleaning & Data Types -> Parquet)
3. Enrichment (Historical Weather data via Open-Meteo)
4. Warehousing (dbt models in Redshift)
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

from enrichment.pipeline import run as run_enrichment

# Import the entry points from our internal modules
from ingestion.pipeline import run as run_ingestion
from processing.pipeline import run as run_processing

default_args = {
    "owner": "data_engineering",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    "delivery_data_pipeline",
    default_args=default_args,
    description="End-to-end pipeline for delivery data.",
    schedule_interval="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["delivery", "ml", "core"],
) as dag:

    # 1. Ingestion Task
    ingest_task = PythonOperator(
        task_id="ingest_raw_data",
        python_callable=run_ingestion,
        op_kwargs={
            # ds is the logical execution date string YYYY-MM-DD
            "ingestion_date": "{{ ds }}"
        }
    )

    # 2. Processing Task
    process_task = PythonOperator(
        task_id="process_delivery_data",
        python_callable=run_processing,
        op_kwargs={
            "ingestion_date": "{{ ds }}",
            "dry_run": False
        }
    )

    # 3. Enrichment Task
    enrich_task = PythonOperator(
        task_id="enrich_weather_data",
        python_callable=run_enrichment,
        op_kwargs={
            "ingestion_date": "{{ ds }}",
            "dry_run": False
        }
    )

    # 4. dbt Tasks (Run & Test)
    # Using BashOperator to call dbt in the warehouse directory
    dbt_run = BashOperator(
        task_id="dbt_run_models",
        bash_command="cd /opt/airflow/warehouse/dbt && dbt run --profiles-dir .",
    )

    dbt_test = BashOperator(
        task_id="dbt_test_models",
        bash_command="cd /opt/airflow/warehouse/dbt && dbt test --profiles-dir .",
    )

    # Define the dependency chain
    ingest_task >> process_task >> enrich_task >> dbt_run >> dbt_test
