# Delivery Data Platform

An end-to-end cloud-native data engineering platform for food delivery analytics, built on AWS.

## Architecture Overview

```text
Historical Delivery Dataset (Kaggle / Zomato)
          │
          ▼
    S3 / Raw Zone
          │
          ▼
  Validation / Profiling
          │
    ┌─────┴─────┐
    ▼           ▼
Delivery    Weather Data
  Data        Source
    │           │
    └─────┬─────┘
          ▼
   S3 / Processed
          │
          ▼
    dbt Transformations
          │
          ▼
       Redshift
          │
   ┌──────┼──────┐
   ▼      ▼      ▼
Analytics Feature  Data
         Store   Marts
```

## AWS Stack

| Layer | Service |
|---|---|
| Storage / Data Lake | Amazon S3 |
| Compute (event-driven) | AWS Lambda |
| Ad-hoc Query | Amazon Athena |
| Data Warehouse | Amazon Redshift Serverless |
| Transformation | dbt |
| Orchestration | Apache Airflow |
| Infrastructure as Code | Terraform |

## Project Phases

| Phase | Description | Status |
|---|---|---|
| 1 | Repository & local environment | ✅ Done |
| 2 | Source ingestion (Kaggle → S3) | 🔲 |
| 3 | AWS infrastructure (Terraform) | 🔲 |
| 4 | Data processing & feature engineering | 🔲 |
| 5 | Weather enrichment | 🔲 |
| 6 | Warehouse & dbt models | 🔲 |
| 7 | Airflow orchestration | 🔲 |
| 8 | Data quality & dbt tests | 🔲 |
| 9 | Analytics marts | 🔲 |
| 10 | ML (delivery-time prediction) | 🔲 |
| 11 | CI/CD (GitHub Actions) | 🔲 |

## Getting Started

### Prerequisites

- Python 3.12
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Docker & Docker Compose
- AWS CLI (configured with appropriate credentials)
- Terraform ≥ 1.9
- Kaggle account + API key

### Local Setup

```bash
# 1. Clone the repository
git clone <repo-url>
cd delivery-data-platform

# 2. Create and activate the Python environment
uv sync --extra dev

# 3. Configure environment variables
cp .env.example .env
# Edit .env and fill in required values

# 4. Verify the environment
uv run python scripts/check_env.py

# 5. Run unit tests
uv run pytest tests/unit/ -v
```

### Starting Airflow Locally

```bash
# First time only — initialise DB and create admin user
docker compose up airflow-init

# Start all services
docker compose up -d

# Open Airflow UI: http://localhost:8080  (admin / admin)

# Stop
docker compose down

# Stop and wipe volumes (full reset)
docker compose down -v
```

## Repository Structure

```text
delivery-data-platform/
├── config/             # Pydantic settings — loaded from environment
├── dags/               # Airflow DAGs
├── dbt/                # dbt models, tests, macros (Phase 6+)
├── ingestion/          # Dataset ingestion scripts (Phase 2+)
├── notebooks/          # Exploratory only — not production code
├── processing/         # Data cleaning & feature engineering (Phase 4+)
├── scripts/            # Utility scripts
├── terraform/          # Infrastructure as Code (Phase 3+)
├── tests/
│   ├── unit/           # pytest unit tests (no AWS required)
│   └── integration/    # Tests requiring real AWS resources
├── validation/         # Schema & data quality checks (Phase 2+)
├── docker-compose.yml  # Local Airflow stack
├── pyproject.toml      # Python project config (uv + ruff + mypy + pytest)
└── .env.example        # Environment variable template
```

## Data Lake Zones

| Zone | S3 Prefix | Description |
|---|---|---|
| Raw | `raw/` | Immutable original files from source |
| Validated | `validated/` | Files that passed schema validation |
| Processed | `processed/` | Cleaned, enriched, feature-engineered data |
| Analytics | `analytics/` | Aggregations and data mart exports |

## Engineering Principles

- **Reproducibility** — infrastructure via Terraform, transformations via code
- **Idempotency** — pipelines are safe to re-run without creating duplicates
- **Data Lineage** — raw data is never overwritten; transformations are traceable
- **Separation of Concerns** — ingestion, validation, transformation, and serving are distinct layers
- **No secrets in source control** — all credentials via environment variables

## Development Workflow

```bash
# Lint + format
uv run ruff check .
uv run ruff format .

# Type check
uv run mypy config/ ingestion/ validation/ processing/

# Tests
uv run pytest tests/unit/ -v
uv run pytest tests/integration/ -v  # requires AWS credentials

# Terraform
cd terraform && terraform fmt && terraform validate
```

## Cost Notes

> [!WARNING]
> The following AWS services generate ongoing costs. Shut them down when not in use:
> - **Redshift Serverless** — billed per RPU-second
> - **Airflow on MWAA** (if used) — billed per hour
>
> This local setup uses Docker Compose for Airflow to avoid MWAA costs during development.

## Data Source

Primary dataset: [Zomato Delivery Operations Analytics Dataset](https://www.kaggle.com/datasets/saurabhbadole/zomato-delivery-operations-analytics-dataset) (Kaggle)

> [!NOTE]
> This dataset is used for demonstration and learning purposes. Its provenance as real-world operational data has not been independently verified.
