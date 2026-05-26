"""End-to-end training pipeline for Azure ML and local execution."""

import argparse
import json
import os
import joblib

try:
    from azureml.core import Run
    AZUREML_AVAILABLE = True
except ImportError:
    AZUREML_AVAILABLE = False
    Run = None
    print("Warning: azureml-core not available. Running in local mode only.")

from src.data.fetch_api_data import (
    build_training_frame_from_env,
    build_training_frame_weather_api_local_from_env,
)
from src.data.load_dataset import load_dataset
from src.data.aggregation import aggregate_daily
from src.data.cleaning import clean_dataset
from src.features.clearsky_features import add_clearsky_to_df_model
from src.features.kc_features import add_kc_to_df
from src.features.time_features import add_time_features
from src.models.split import train_test_split_by_date
from src.models.train_linear_model import train_model
from src.models.predict import scale_features, make_predictions
from src.models.evaluate_model import evaluate_model


def _to_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def parse_args():
    parser = argparse.ArgumentParser(description="PV training pipeline")
    parser.add_argument(
        "--data_source",
        choices=["api", "file", "weather_api_local_production"],
        default="weather_api_local_production",
        help="Use full API ingestion, local file loading, or weather API + local production.",
    )
    parser.add_argument(
        "--input_path",
        default="data/raw/dfmodelpierrerozir.csv",
        help="Dataset path used when data_source=file.",
    )
    parser.add_argument(
        "--start_date",
        default="2018-01-01",
        help="Start date used for API ingestion (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--end_date",
        default="2021-12-31",
        help="End date used for API ingestion (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--latitude",
        type=float,
        default=48.7667,
        help="Site latitude for Open-Meteo weather API (default: Bussy-Saint-Georges).",
    )
    parser.add_argument(
        "--longitude",
        type=float,
        default=2.6667,
        help="Site longitude for Open-Meteo weather API (default: Bussy-Saint-Georges).",
    )
    parser.add_argument(
        "--split_date",
        default="2020-07-31",
        help="Train/test split date.",
    )
    parser.add_argument(
        "--register_model",
        default="true",
        help="Register model in Azure ML registry (true/false).",
    )
    return parser.parse_args()


def run_pipeline(
    data_source="weather_api_local_production",
    input_path="data/raw/dfmodelpierrerozir.csv",
    start_date="2018-01-01",
    end_date="2021-12-31",
    latitude=48.7667,
    longitude=2.6667,
    split_date="2020-07-31",
    register_model=True,
):
    run = Run.get_context() if AZUREML_AVAILABLE else None

    # 1. load raw dataset depending on selected ingestion mode
    if data_source == "api":
        df = build_training_frame_from_env(start_date=start_date, end_date=end_date)
        print(
            "Automatic ingestion enabled: Open-Meteo + production API "
            f"for {start_date} to {end_date}"
        )
    elif data_source == "weather_api_local_production":
        df = build_training_frame_weather_api_local_from_env(
            start_date=start_date,
            end_date=end_date,
            production_file_path=input_path,
            latitude=latitude,
            longitude=longitude,
        )
        print(
            "Hybrid ingestion enabled: Open-Meteo API + local production file "
            f"for {start_date} to {end_date}"
        )
    else:
        df = load_dataset(input_path)
        print(f"Local ingestion enabled from: {input_path}")

    # 2. feature engineering (hourly to daily)
    df = add_clearsky_to_df_model(df)
    df = add_kc_to_df(df, ghi_col="shortwave_radiation")
    df_daily = aggregate_daily(df)

    # 3. cleaning/thresholding
    df_clean = clean_dataset(df_daily, min_production_wh=1000.0)

    # 4. add calendar features
    df_final = add_time_features(df_clean)

    # 5. prepare X/y
    target = "PV_ELE_IME_I_001"
    features = [
        "direct_radiation",
        "diffuse_radiation",
        "shortwave_radiation",
        "cs_ghi",
        "kc_day",
        "day_of_year_sin",
        "day_of_year_cos",
    ]

    X = df_final[features]
    y = df_final[target]

    # 6. date-based split
    X_train, X_test, y_train, y_test = train_test_split_by_date(
        X, y, split_date=split_date
    )

    # 7. scale
    scaler, X_train_scaled, X_test_scaled = scale_features(X_train, X_test)

    # 8. train
    model = train_model(X_train_scaled, y_train)

    # 9. predict + evaluate
    y_pred = make_predictions(model, X_test_scaled)
    r2, mae, rmse = evaluate_model(y_test, y_pred)

    print(f"Train/test split date: {split_date}")
    print(f"Train samples  : {len(X_train)}")
    print(f"Test samples   : {len(X_test)}")
    print(f"R2   : {r2:.3f}")
    print(f"MAE  : {mae:.1f} Wh/day")
    print(f"RMSE : {rmse:.1f} Wh/day")

    # Step 3: log metrics in Azure ML
    if AZUREML_AVAILABLE and run:
        run.log("R2", float(r2))
        run.log("MAE", float(mae))
        run.log("RMSE", float(rmse))

    # Save a full inference bundle in outputs/; Azure ML uploads this directory automatically.
    os.makedirs("outputs", exist_ok=True)

    model_path = os.path.join("outputs", "model.pkl")
    scaler_path = os.path.join("outputs", "scaler.pkl")
    metadata_path = os.path.join("outputs", "metadata.json")
    
    joblib.dump(model, model_path)
    joblib.dump(scaler, scaler_path)
    with open(metadata_path, "w", encoding="utf-8") as metadata_file:
        json.dump(
            {
                "model_type": "LinearRegression",
                "target": target,
                "features": features,
                "split_date": split_date,
                "metrics": {
                    "r2": float(r2),
                    "mae": float(mae),
                    "rmse": float(rmse),
                },
                "coefficients": model.coef_.tolist(),
                "intercept": float(model.intercept_),
            },
            metadata_file,
            indent=2,
        )

    # Step 4: register model in Azure ML model registry
    if register_model and AZUREML_AVAILABLE and run:
        registered_model = run.register_model(
            model_name="pv-production-model",
            model_path="outputs",
            tags={"framework": "sklearn", "model_type": "linear_regression"},
            properties={"split_date": str(split_date)},
            description="Linear regression PV production model",
        )
        print(
            f"Registered model: {registered_model.name} v{registered_model.version}"
        )
    elif register_model and not AZUREML_AVAILABLE:
        print("Model registration skipped: Azure ML not available")

    return {
        "model": model,
        "scaler": scaler,
        "r2": r2,
        "mae": mae,
        "rmse": rmse,
        "X_test": X_test,
        "y_test": y_test,
        "y_pred": y_pred,
        "model_path": model_path,
        "scaler_path": scaler_path,
        "metadata_path": metadata_path,
    }


if __name__ == "__main__":
    args = parse_args()
    run_pipeline(
        data_source=args.data_source,
        input_path=args.input_path,
        start_date=args.start_date,
        end_date=args.end_date,
        latitude=args.latitude,
        longitude=args.longitude,
        split_date=args.split_date,
        register_model=_to_bool(args.register_model),
    )