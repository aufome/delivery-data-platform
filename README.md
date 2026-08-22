# Delivery Data Platform

A data engineering platform for food delivery analytics, built on AWS.

Ingests historical delivery data from Kaggle, validates and enriches it with external weather data, models it in a dimensional warehouse, and exposes it for analytics and machine learning.

## Stack

| Layer | Technology |
|---|---|
| Data lake | Amazon S3 |
| Compute | AWS Lambda |
| Ad-hoc query | Amazon Athena |
| Warehouse | Amazon Redshift Serverless |
| Transformation | dbt |
| Orchestration | Apache Airflow |
| Infrastructure | Terraform |

## Architecture

```
Kaggle Dataset → S3 Raw → Validation → Enrichment (Weather API)
                                              ↓
                                        S3 Processed
                                              ↓
                                     dbt → Redshift
                                              ↓
                               Analytics | Feature Store | Data Marts
```

## Getting Started

### Prerequisites

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- Docker and Docker Compose
- AWS CLI
- Terraform ≥ 1.9
- Kaggle account and API key

### Setup

```bash
git clone <repo-url>
cd delivery-data-platform

uv sync --extra dev

cp .env.example .env
# Fill in the required values in .env

uv run python scripts/check_env.py
uv run pytest tests/unit/ -v
```

### Local Airflow

```bash
# First run only
docker compose up airflow-init

docker compose up -d
# UI available at http://localhost:8080  (admin / admin)

docker compose down       # stop
docker compose down -v    # stop and reset volumes
```

## Repository Layout

```
config/         Pydantic settings loaded from environment variables
dags/           Airflow DAGs
dbt/            dbt models, tests, macros
ingestion/      Kaggle download and S3 upload
processing/     Cleaning, enrichment, feature engineering
validation/     Schema and data quality checks
scripts/        Utility scripts
terraform/      Infrastructure as Code
tests/
  unit/         No AWS credentials required
  integration/  Requires real AWS resources
```

## Data Lake Zones

| Zone | Prefix | Purpose |
|---|---|---|
| Raw | `raw/` | Immutable source files |
| Validated | `validated/` | Files that passed schema checks |
| Processed | `processed/` | Cleaned and enriched data |
| Analytics | `analytics/` | Mart exports |

## Development

```bash
uv run ruff check .           # lint
uv run ruff format .          # format
uv run mypy config/ ingestion/ validation/ processing/
uv run pytest tests/unit/ -v
```

## Data Source

[Zomato Delivery Operations Analytics Dataset](https://www.kaggle.com/datasets/saurabhbadole/zomato-delivery-operations-analytics-dataset) — used for demonstration purposes. Provenance as real operational data has not been independently verified.
