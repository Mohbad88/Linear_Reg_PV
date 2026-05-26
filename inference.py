"""Download registered model from Azure ML and run inference."""

from datetime import date, datetime
import json
import joblib
import numpy as np
import pandas as pd
import pvlib
import requests
import time
from azureml.core import Workspace, Model
from pathlib import Path


def load_model_from_registry(model_name="pv-production-model", version=None):
    """Load registered model from Azure ML registry."""
    
    # Connect to workspace
    ws = Workspace.from_config(path="config.json")
    
    # Load model
    if version:
        model = Model(ws, name=model_name, version=version)
    else:
        # Get latest version
        models = Model.list(ws, name=model_name)
        model = models[0]  # Latest version
    
    # Download model files
    model_download_path = model.download(target_dir="downloaded_model", exist_ok=True)
    root_path = Path(model_download_path)
    model_root = root_path.parent if root_path.is_file() else root_path

    print(f"Model files downloaded to: {model_root}")

    # Azure can package files at root or in nested folders (e.g. outputs/)
    # so we scan recursively for a complete inference bundle.
    model_candidates = sorted(model_root.rglob("model.pkl"))

    selected_bundle_dir = None
    for candidate in model_candidates:
        candidate_dir = candidate.parent
        if (candidate_dir / "scaler.pkl").exists() and (candidate_dir / "metadata.json").exists():
            selected_bundle_dir = candidate_dir
            break

    # If no complete bundle is found, keep backward compatibility:
    # load model from registry and try scaler/metadata from local outputs.
    if selected_bundle_dir is None:
        if not model_candidates:
            raise FileNotFoundError(
                f"No model.pkl found in downloaded registry model at {model_root}."
            )

        model_path = model_candidates[0]
        print(f"Loading model from: {model_path}")
        model_obj = joblib.load(str(model_path))

        print("scaler.pkl/metadata.json not found in registered model, trying local outputs fallback...")
        local_scaler_path = Path("outputs") / "scaler.pkl"
        local_metadata_path = Path("outputs") / "metadata.json"

        if not local_scaler_path.exists() or not local_metadata_path.exists():
            raise FileNotFoundError(
                "Missing scaler.pkl or metadata.json. "
                "Either run training again with the latest registration fix, "
                "or pass a model version that contains the full bundle."
            )

        scaler = joblib.load(str(local_scaler_path))
        with open(local_metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
    else:
        model_path = selected_bundle_dir / "model.pkl"
        scaler_path = selected_bundle_dir / "scaler.pkl"
        metadata_path = selected_bundle_dir / "metadata.json"

        print(f"Loading full bundle from: {selected_bundle_dir}")
        model_obj = joblib.load(str(model_path))
        scaler = joblib.load(str(scaler_path))
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
    
    return model_obj, scaler, metadata


def make_inference(model, scaler, metadata, input_data):
    """
    Make predictions.
    
    Args:
        model: Trained LinearRegression model
        scaler: StandardScaler instance
        metadata: Model metadata dict
        input_data: dict or DataFrame with features
    
    Returns:
        dict with predictions and metadata
    """
    
    # Convert to DataFrame if dict
    if isinstance(input_data, dict):
        X = pd.DataFrame(input_data)
    else:
        X = input_data
    
    # Validate features
    required_features = metadata["features"]
    missing = set(required_features) - set(X.columns)
    
    if missing:
        raise ValueError(f"Missing features: {missing}")
    
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

    return {
        "predictions": predictions.tolist(),
        "n_samples": len(predictions),
        "target": metadata["target"],
        "features_used": required_features,
        "model_metrics": metadata["metrics"],
        "coefficients": metadata.get("coefficients"),
        "intercept": metadata.get("intercept"),
        "explanations": explanations,
    }


def fetch_open_meteo_hourly(lat, lon, target_date):
    """Fetch hourly radiation variables from Open-Meteo for one day."""

    target_day = datetime.strptime(target_date, "%Y-%m-%d").date()
    api_url = (
        "https://archive-api.open-meteo.com/v1/archive"
        if target_day < date.today()
        else "https://api.open-meteo.com/v1/forecast"
    )
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": target_date,
        "end_date": target_date,
        "timezone": "UTC",
        "hourly": "shortwave_radiation,direct_radiation,diffuse_radiation",
    }

    payload = None
    last_error = None

    # Open-Meteo can occasionally return transient 5xx (e.g., 502).
    # Retry a few times with exponential backoff before failing.
    for attempt in range(1, 4):
        try:
            resp = requests.get(api_url, params=params, timeout=30)
            if resp.status_code >= 500:
                resp.raise_for_status()
            payload = resp.json()
            break
        except requests.RequestException as exc:
            last_error = exc
            if attempt < 3:
                wait_seconds = 2 ** (attempt - 1)
                print(
                    f"Open-Meteo temporary error ({exc}). "
                    f"Retry {attempt}/3 in {wait_seconds}s..."
                )
                time.sleep(wait_seconds)

    if payload is None:
        raise RuntimeError(
            "Open-Meteo API unavailable after retries. "
            "Please rerun in a few minutes."
        ) from last_error

    if "hourly" not in payload or "time" not in payload["hourly"]:
        raise ValueError("Open-Meteo response has no hourly data")

    hourly = payload["hourly"]
    df = pd.DataFrame(
        {
            "time": hourly["time"],
            "shortwave_radiation": hourly["shortwave_radiation"],
            "direct_radiation": hourly["direct_radiation"],
            "diffuse_radiation": hourly["diffuse_radiation"],
        }
    )
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df = df.set_index("time").sort_index()

    return df


def build_daily_features_from_open_meteo(lat, lon, target_date):
    """Build one-row feature frame aligned with training pipeline expectations."""

    hourly_df = fetch_open_meteo_hourly(lat=lat, lon=lon, target_date=target_date)

    # Build clearsky GHI on the same hourly index, then aggregate to daily sums.
    loc = pvlib.location.Location(latitude=lat, longitude=lon, tz="UTC")
    cs = loc.get_clearsky(hourly_df.index)
    cs_ghi_daily = float(cs["ghi"].sum())

    direct_daily = float(hourly_df["direct_radiation"].sum())
    diffuse_daily = float(hourly_df["diffuse_radiation"].sum())
    shortwave_daily = float(hourly_df["shortwave_radiation"].sum())

    kc_day = shortwave_daily / cs_ghi_daily if cs_ghi_daily > 0 else 0.0
    day_of_year = pd.Timestamp(target_date).dayofyear

    X = pd.DataFrame(
        {
            "direct_radiation": [direct_daily],
            "diffuse_radiation": [diffuse_daily],
            "shortwave_radiation": [shortwave_daily],
            "cs_ghi": [cs_ghi_daily],
            "kc_day": [kc_day],
            "day_of_year_sin": [float(np.sin(2 * np.pi * day_of_year / 365))],
            "day_of_year_cos": [float(np.cos(2 * np.pi * day_of_year / 365))],
        }
    )

    return X


if __name__ == "__main__":
    
    # Download model from Azure ML
    print("Downloading model from Azure ML registry...")
    model, scaler, metadata = load_model_from_registry(model_name="pv-production-model")
    
    print(f"\nModel loaded:")
    print(f"  Target: {metadata['target']}")
    print(f"  Features: {metadata['features']}")
    print(f"  Metrics: {metadata['metrics']}")
    
    # Daily inference using Open-Meteo forecast data
    print("\n" + "="*50)
    print("Running daily inference from Open-Meteo...")
    print("="*50)

    lat = 48.7667
    lon = 2.6667
    target_date = "2021-02-02"

    print(f"Location: lat={lat}, lon={lon}")
    print(f"Target date (UTC): {target_date}")

    X_today = build_daily_features_from_open_meteo(
        lat=lat,
        lon=lon,
        target_date=target_date,
    )

    result = make_inference(model, scaler, metadata, X_today)
    result["inference_context"] = {
        "source": "open-meteo",
        "lat": lat,
        "lon": lon,
        "date": target_date,
    }
    
    # Add fields required by log_prediction_errors.py
    result["predicted_production_wh"] = float(result["predictions"][0]) if result["predictions"] else 0
    result["prediction_date"] = target_date
    
    print("\nResults:")
    print(json.dumps(result, indent=2))
    
    # Save results
    with open("inference_results.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    
    print("\nResults saved to: inference_results.json")
