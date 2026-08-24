"""
FastAPI application for serving the XGBoost Delivery Duration model.
"""

import os
import tempfile
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import joblib  # type: ignore
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from config.settings import get_settings
from processing.s3_client import download_file

# Global variable to store our ML pipeline in memory
ML_PIPELINE = None


class DeliveryPredictionRequest(BaseModel):
    """Schema for incoming delivery prediction requests."""
    straight_line_distance: float = Field(..., description="Distance between restaurant and delivery location in km")
    temperature: float = Field(..., description="Current temperature in Celsius")
    precipitation: float = Field(..., description="Current precipitation in mm")
    wind_speed: float = Field(..., description="Wind speed in km/h")
    humidity: float = Field(..., description="Relative humidity percentage")
    delivery_person_age: int = Field(..., description="Age of the courier")
    delivery_person_ratings: float = Field(..., description="Average rating of the courier")
    vehicle_condition: int = Field(..., description="Condition of the vehicle (0, 1, 2)")
    base_weather_conditions: str = Field(..., description="e.g. Sunny, Stormy, Sandstorms")
    road_traffic_density: str = Field(..., description="e.g. Low, Medium, High, Jam")
    type_of_vehicle: str = Field(..., description="e.g. motorcycle, scooter, electric_scooter")
    type_of_order: str = Field(..., description="e.g. Snack, Meal, Drinks, Buffet")
    city_type: str = Field(..., description="e.g. Metropolitian, Urban, Semi-Urban")
    is_weekend: int = Field(..., description="1 if weekend, 0 otherwise")
    is_peak_hour: int = Field(..., description="1 if peak hour, 0 otherwise")
    multiple_deliveries: int = Field(..., description="Number of additional deliveries")


class DeliveryPredictionResponse(BaseModel):
    """Schema for prediction response."""
    estimated_delivery_duration_minutes: float
    model_version: str


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifecycle event: Load the model from S3 into memory on startup."""
    global ML_PIPELINE
    s = get_settings()

    # In a real environment, you might pass the specific model version as an env var.
    # Here we default to "latest".
    version = os.getenv("MODEL_VERSION", "latest")
    s3_key = f"{s.s3_models_path('delivery_duration')}/version={version}/xgboost_delivery_duration_model.joblib"

    tmp_path = Path(tempfile.gettempdir()) / "xgboost_model.joblib"

    try:
        # We try to download from S3
        download_file(s.s3_bucket_name, s3_key, tmp_path, region=s.aws_region)
        ML_PIPELINE = joblib.load(tmp_path)
        print(f"Model successfully loaded from {s3_key}")
    except Exception as e:
        print(f"Warning: Failed to load model from S3 ({e}). The API will return 503 until a model is provided.")
        # If running locally without S3 access, we check if there's a local mock/test model
        local_test_model = Path("xgboost_delivery_duration_model.joblib")
        if local_test_model.exists():
            ML_PIPELINE = joblib.load(local_test_model)
            print("Loaded local fallback model.")

    yield

    # Cleanup on shutdown
    ML_PIPELINE = None


app = FastAPI(
    title="Delivery Time Prediction API",
    description="Real-time inference API for estimating food delivery times using XGBoost.",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/health")
def health_check() -> dict[str, Any]:
    """Check if the API and model are ready."""
    if ML_PIPELINE is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    return {"status": "ok", "model_loaded": True}


@app.post("/predict", response_model=DeliveryPredictionResponse)
def predict_delivery_time(request: DeliveryPredictionRequest) -> DeliveryPredictionResponse:
    """Predict delivery duration based on order, courier, and weather features."""
    if ML_PIPELINE is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    # Convert Pydantic model to Pandas DataFrame (expected by our scikit-learn pipeline)
    input_data = pd.DataFrame([request.model_dump()])

    try:
        # Pipeline handles imputation, scaling, one-hot encoding, and XGBoost prediction automatically
        prediction = ML_PIPELINE.predict(input_data)

        return DeliveryPredictionResponse(
            estimated_delivery_duration_minutes=round(float(prediction[0]), 2),
            model_version=os.getenv("MODEL_VERSION", "latest")
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Prediction failed: {str(e)}") from e
