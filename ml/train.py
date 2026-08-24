"""
Machine Learning training module for delivery duration prediction.

Loads the enriched delivery data from S3, constructs a preprocessing pipeline
using scikit-learn, trains an XGBoost regressor, evaluates the metrics,
and saves the compiled pipeline artifact to S3.

Usage:
    uv run python -m ml.train --ingestion-date 2024-01-15
    uv run python -m ml.train --local-file path/to/enriched.parquet --dry-run
"""

import argparse
import sys
import tempfile
from pathlib import Path

import joblib
import pandas as pd
import structlog
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBRegressor

from config.settings import get_settings
from processing.s3_client import download_file, upload_file

log = structlog.get_logger(__name__)


def load_data(
    ingestion_date: str | None,
    local_file: Path | None,
    tmp_dir: Path
) -> pd.DataFrame:
    """Load the enriched Parquet dataset from S3 or local path."""
    if local_file:
        log.info("ml.load_data.local", path=str(local_file))
        return pd.read_parquet(local_file)

    if not ingestion_date:
        raise ValueError("Must provide either --local-file or --ingestion-date.")

    s = get_settings()
    s3_key = f"{s.s3_processed_path('enriched_delivery_orders')}/source=zomato/ingestion_date={ingestion_date}/delivery_data.parquet"
    local_path = tmp_dir / "enriched_data.parquet"

    log.info("ml.load_data.s3", bucket=s.s3_bucket_name, key=s3_key)
    download_file(s.s3_bucket_name, s3_key, local_path, region=s.aws_region)

    return pd.read_parquet(local_path)


def build_pipeline() -> Pipeline:
    """Build the scikit-learn preprocessing and modeling pipeline."""
    numeric_features = [
        "straight_line_distance",
        "temperature",
        "precipitation",
        "wind_speed",
        "humidity",
        "delivery_person_age",
        "delivery_person_ratings",
        "vehicle_condition"
    ]

    categorical_features = [
        "base_weather_conditions",
        "road_traffic_density",
        "type_of_vehicle",
        "type_of_order",
        "city_type"
    ]

    # Booleans or already numeric encoded that don't need scaling
    passthrough_features = [
        "is_weekend",
        "is_peak_hour",
        "multiple_deliveries"
    ]

    numeric_transformer = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler())
    ])

    categorical_transformer = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="constant", fill_value="missing")),
        ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False))
    ])

    passthrough_transformer = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="constant", fill_value=0))
    ])

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", numeric_transformer, numeric_features),
            ("cat", categorical_transformer, categorical_features),
            ("pass", passthrough_transformer, passthrough_features)
        ],
        remainder="drop" # Drop anything else like IDs or dates
    )

    pipeline = Pipeline(steps=[
        ("preprocessor", preprocessor),
        ("regressor", XGBRegressor(
            n_estimators=150,
            learning_rate=0.1,
            max_depth=6,
            random_state=42,
            n_jobs=-1
        ))
    ])

    return pipeline


def evaluate_model(y_true: pd.Series, y_pred: pd.Series) -> dict[str, float]:
    """Calculate evaluation metrics."""
    mae = mean_absolute_error(y_true, y_pred)
    rmse = root_mean_squared_error(y_true, y_pred)
    r2 = r2_score(y_true, y_pred)
    return {"mae": mae, "rmse": rmse, "r2": r2}


def run(
    *,
    ingestion_date: str | None = None,
    local_file: Path | None = None,
    dry_run: bool = False,
) -> None:
    s = get_settings()
    log.info("ml.train.start", ingestion_date=ingestion_date, dry_run=dry_run)

    with tempfile.TemporaryDirectory(prefix="ddp_ml_") as tmp:
        tmp_dir = Path(tmp)

        # 1. Load Data
        df = load_data(ingestion_date, local_file, tmp_dir)

        # Drop rows where target is missing
        target_col = "delivery_duration"
        if target_col not in df.columns:
            raise ValueError(f"Target column '{target_col}' not found in dataset.")

        df = df.dropna(subset=[target_col])
        log.info("ml.data.loaded", rows=len(df), cols=len(df.columns))

        # 2. Split Data (Chronological/Temporal Split)
        # Sort by order_date to ensure we train on past data and test on future data
        # to prevent data leakage and accurately simulate real-world prediction.
        if "order_date" in df.columns:
            df = df.sort_values("order_date")
            
        X = df.drop(columns=[target_col])
        y = df[target_col]

        split_idx = int(len(df) * 0.8)
        X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
        
        log.info("ml.data.split.chronological", train_rows=len(X_train), test_rows=len(X_test))

        # 3. Build & Train
        pipeline = build_pipeline()
        log.info("ml.train.fitting")
        pipeline.fit(X_train, y_train)

        # 4. Evaluate
        log.info("ml.train.evaluating")
        y_pred = pipeline.predict(X_test)
        metrics = evaluate_model(y_test, y_pred)
        log.info("ml.metrics", **metrics)

        # 5. Export & Upload
        model_filename = "xgboost_delivery_duration_model.joblib"
        local_model_path = tmp_dir / model_filename

        log.info("ml.export.saving_locally", path=str(local_model_path))
        joblib.dump(pipeline, local_model_path)

        if dry_run:
            log.info("ml.export.dry_run.skipped_upload")
        else:
            target_date = ingestion_date or "latest"
            s3_key = f"{s.s3_models_path('delivery_duration')}/version={target_date}/{model_filename}"
            upload_file(local_model_path, s.s3_bucket_name, s3_key, region=s.aws_region)
            log.info("ml.export.uploaded", s3_key=s3_key)

    log.info("ml.train.complete")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train XGBoost delivery duration model.")
    parser.add_argument("--ingestion-date", type=str)
    parser.add_argument("--local-file", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = _parse_args()
    try:
        run(ingestion_date=args.ingestion_date, local_file=args.local_file, dry_run=args.dry_run)
    except Exception as e:
        log.error("ml.train.failed", error=str(e))
        sys.exit(1)
