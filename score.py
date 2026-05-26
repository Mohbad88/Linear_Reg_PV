"""Inference script for PV production model."""

import json
import joblib
import pandas as pd
import numpy as np
import os


def init():
    """Load model and scaler on startup."""
    global model, scaler, metadata

    # In Azure ML endpoint, the model is in AZUREML_MODEL_DIR
    # Locally, it's in outputs/
    model_dir = os.environ.get("AZUREML_MODEL_DIR", "outputs")

    model_path = os.path.join(model_dir, "model.pkl")
    scaler_path = os.path.join(model_dir, "scaler.pkl")
    metadata_path = os.path.join(model_dir, "metadata.json")

    print(f"Loading model from: {model_dir}")

    model = joblib.load(model_path)
    scaler = joblib.load(scaler_path)

    with open(metadata_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    print("Model, scaler, and metadata loaded successfully.")
    print(f"Model features: {metadata['features']}")


def run(raw_data):
    """
    Make predictions on input data.

    Input:
        raw_data: JSON string or pandas DataFrame with required features

    Output:
        Dictionary with predictions and metadata
    """
    try:
        # Parse input
        if isinstance(raw_data, str):
            data = json.loads(raw_data)
            X = pd.DataFrame(data)
        else:
            X = raw_data

        # Validate features
        required_features = metadata["features"]
        missing_features = set(required_features) - set(X.columns)
        if missing_features:
            return {
                "error": f"Missing features: {missing_features}",
                "required_features": required_features,
            }

        # Select and order features
        X_selected = X[required_features].copy()

        # Scale
        X_scaled = scaler.transform(X_selected)

        # Predict
        predictions = model.predict(X_scaled)

        coefficients = np.asarray(metadata.get("coefficients", []), dtype=float)
        intercept = float(metadata.get("intercept", 0.0))
        explanations = []

        if len(coefficients) == len(required_features):
            for row_idx in range(len(X_selected)):
                raw_values = {
                    feature: float(X_selected.iloc[row_idx][feature])
                    for feature in required_features
                }
                scaled_values = {
                    feature: float(X_scaled[row_idx, feature_idx])
                    for feature_idx, feature in enumerate(required_features)
                }
                contributions = {
                    feature: float(coefficients[feature_idx] * X_scaled[row_idx, feature_idx])
                    for feature_idx, feature in enumerate(required_features)
                }

                explanations.append(
                    {
                        "raw_features": raw_values,
                        "scaled_features": scaled_values,
                        "feature_contributions": contributions,
                        "intercept": intercept,
                        "prediction": float(predictions[row_idx]),
                    }
                )

        # Return results
        return {
            "predictions": predictions.tolist(),
            "target": metadata["target"],
            "model_metrics": metadata["metrics"],
            "n_samples": len(predictions),
            "coefficients": metadata.get("coefficients"),
            "intercept": metadata.get("intercept"),
            "explanations": explanations,
        }

    except Exception as e:
        return {"error": str(e)}


# Example usage locally
if __name__ == "__main__":
    # Initialize
    init()

    # Example prediction
    example_input = {
        "direct_radiation": [100, 150, 200],
        "diffuse_radiation": [50, 75, 100],
        "shortwave_radiation": [150, 225, 300],
        "cs_ghi": [120, 180, 240],
        "kc_day": [0.8, 0.85, 0.9],
        "day_of_year_sin": [0.2, 0.3, 0.4],
        "day_of_year_cos": [0.95, 0.93, 0.91],
    }

    result = run(json.dumps(example_input))
    print(json.dumps(result, indent=2))
