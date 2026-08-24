"""
Unit tests for the Machine Learning training pipeline.
"""

import pandas as pd
from sklearn.pipeline import Pipeline

from ml.train import build_pipeline, evaluate_model


def test_build_pipeline() -> None:
    """Ensure the pipeline builds successfully and has correct steps."""
    pipeline = build_pipeline()

    assert isinstance(pipeline, Pipeline)
    assert "preprocessor" in pipeline.named_steps
    assert "regressor" in pipeline.named_steps


def test_pipeline_fit_predict() -> None:
    """Test the pipeline on dummy data to ensure transformers don't crash."""
    pipeline = build_pipeline()

    # Create minimal mock dataframe
    df = pd.DataFrame({
        "straight_line_distance": [5.2, None, 1.1],
        "temperature": [22.0, 15.5, 30.1],
        "precipitation": [0.0, 1.2, 0.0],
        "wind_speed": [5.1, 12.0, 3.3],
        "humidity": [50.0, 80.0, 40.0],
        "delivery_person_age": [25, 30, 22],
        "delivery_person_ratings": [4.5, 4.8, 3.9],
        "vehicle_condition": [2, 1, 0],

        "base_weather_conditions": ["Sunny", "Rainy", None],
        "road_traffic_density": ["Low", "High", "Medium"],
        "type_of_vehicle": ["motorcycle", "scooter", "motorcycle"],
        "type_of_order": ["Snack", "Meal", "Meal"],
        "city_type": ["Metropolitian", "Urban", "Semi-Urban"],

        "is_weekend": [0, 1, 0],
        "is_peak_hour": [1, 0, 1],
        "multiple_deliveries": [0, 1, 0]
    })

    y = pd.Series([25.0, 45.0, 15.0])

    # Fit
    pipeline.fit(df, y)

    # Predict
    preds = pipeline.predict(df)

    assert len(preds) == 3
    # With a tree and 3 samples, it should fit fairly well, but we just check shapes
    assert preds.shape == (3,)


def test_evaluate_model() -> None:
    """Test metrics calculation."""
    y_true = pd.Series([10.0, 20.0, 30.0])
    y_pred = pd.Series([12.0, 20.0, 25.0])

    metrics = evaluate_model(y_true, y_pred)

    assert "mae" in metrics
    assert "rmse" in metrics
    assert "r2" in metrics

    # MAE = (|10-12| + |20-20| + |30-25|) / 3 = (2 + 0 + 5) / 3 = 7 / 3 = 2.333
    assert abs(metrics["mae"] - 2.333) < 0.01
