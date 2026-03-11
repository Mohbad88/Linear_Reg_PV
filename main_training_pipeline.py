"""End-to-end training pipeline inspired by the original notebook.

This script is intended to be executed from the repository root; it builds a
model using a date-based train/test split and prints evaluation metrics.  The
various steps live in the ``src`` package so that they can also be imported
from notebooks or tests.
"""

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
from src.visualization.plot_predictions import plot_one_test_day_bar_plots, plot_real_vs_pred


def run_pipeline(
    input_path: str = "data/raw/df_model_Pierre_ozoir.pkl",
    split_date: str = "2020-07-31",
):
    # 1. load raw dataset
    df = load_dataset(input_path)

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
        'direct_radiation',
        'diffuse_radiation',
        'shortwave_radiation',
        'cs_ghi',
        'kc_day',
        'day_of_year_sin',
        'day_of_year_cos',
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
    print(f"R²   : {r2:.3f}")
    print(f"MAE  : {mae:.1f} Wh/day")
    print(f"RMSE : {rmse:.1f} Wh/day")

    # 10. optional visualization (example day and overall scatter)
    plot_one_test_day_bar_plots(str(X_test.index[0].date()), y_test, y_pred)
    plot_real_vs_pred(y_test, y_pred)

    return {
        'model': model,
        'scaler': scaler,
        'r2': r2,
        'mae': mae,
        'rmse': rmse,
        'X_test': X_test,
        'y_test': y_test,
        'y_pred': y_pred,
    }


if __name__ == '__main__':
    run_pipeline()