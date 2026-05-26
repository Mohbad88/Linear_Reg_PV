"""Phase 4: Log Prediction Errors - Compare predictions vs actual production."""

from datetime import datetime, timedelta
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from src.data.fetch_api_data import build_training_frame_weather_api_local_from_env
from src.data.aggregation import aggregate_daily
from src.features.clearsky_features import add_clearsky_to_df_model
from src.features.kc_features import add_kc_to_df
from src.features.time_features import add_time_features


def load_yesterday_prediction():
    """Load prediction made yesterday from inference_results.json"""
    try:
        with open("inference_results.json", "r") as f:
            data = json.load(f)
        yesterday_prediction = data.get("predicted_production_wh")
        prediction_date = data.get("prediction_date")
        
        if yesterday_prediction is None or prediction_date is None:
            print(" ERROR: inference_results.json is missing required fields")
            print("   Expected fields: 'predicted_production_wh', 'prediction_date'")
            return None, None
        
        return yesterday_prediction, prediction_date
    except FileNotFoundError:
        print(" ERROR: inference_results.json not found")
        print("   Please run inference.py first to generate predictions")
        print("   Command: python inference.py")
        return None, None
    except json.JSONDecodeError as e:
        print(f" ERROR: inference_results.json is not valid JSON: {e}")
        return None, None


def get_actual_production_yesterday(prediction_date, production_file="data/processed/df_daily_cleaned.csv", production_column="PV_ELE_IME_I_001"):
    """Load actual production data for the predicted date"""
    try:
        # Load CSV with index_col=0 to treat first column (dates) as index
        df = pd.read_csv(production_file, index_col=0)
        
        # Reset index to make dates a regular column
        df.reset_index(inplace=True)
        df.rename(columns={df.columns[0]: 'date'}, inplace=True)
        
        # Parse dates
        df['date'] = pd.to_datetime(df['date'])
        date_col = 'date'
        
        # Parse dates
        df[date_col] = pd.to_datetime(df[date_col])
        
        # Get date range info
        min_date = df[date_col].dt.date.min()
        max_date = df[date_col].dt.date.max()
        
        print(f"   CSV date range: {min_date} to {max_date}")
        print(f"   Looking for date: {prediction_date}")
        
        # Filter for the prediction date
        df_target = df[df[date_col].dt.date == prediction_date]
        
        if df_target.empty:
            print(f"\nERROR: No production data found for {prediction_date}")
            print(f"   File: {production_file}")
            print(f"   Date column: '{date_col}'")
            print(f"   Production column: '{production_column}'")
            print(f"   CSV contains dates from {min_date} to {max_date}")
            print(f"   Requested date {prediction_date} is NOT in the CSV range")
            return None
        
        # Check if production column exists
        if production_column not in df.columns:
            print(f"\nERROR: Column '{production_column}' not found")
            print(f"   Available columns: {df.columns.tolist()}")
            return None
        
        # Get production value for that date
        actual_production = df_target[production_column].sum()
        
        print(f"    Found {len(df_target)} record(s) for {prediction_date}")
        print(f"   Production column '{production_column}': {actual_production:.1f} Wh")
        
        return actual_production
        
    except FileNotFoundError:
        print(f"\n ERROR: Production file not found: {production_file}")
        return None
    except Exception as e:
        print(f"\n ERROR: Failed to load production data: {e}")
        print(f"   File: {production_file}")
        if 'df' in locals():
            print(f"   Columns found: {df.columns.tolist()}")
        return None


def calculate_errors(predicted, actual):
    """Calculate prediction errors."""
    error = predicted - actual
    mae = abs(error)
    error_percent = (error / actual * 100) if actual != 0 else 0
    
    # Determine if over or under-estimation
    if error > 0:
        estimation_type = "OVERESTIMATION"
    elif error < 0:
        estimation_type = "UNDERESTIMATION"
    else:
        estimation_type = "EXACT"
    
    return {
        "error_wh": error,
        "mae_wh": mae,
        "error_percent": error_percent,
        "estimation_type": estimation_type,
        "predicted_wh": predicted,
        "actual_wh": actual
    }


def log_prediction_errors():
    """Main function: compare prediction vs actual and log errors."""
    
    print("\n" + "="*60)
    print("Phase 4: Log Prediction Errors")
    print("="*60)
    
    # Load yesterday's prediction (which was for today)
    predicted_production, prediction_date_str = load_yesterday_prediction()
    
    if predicted_production is None:
        print("  Cannot calculate errors: no previous prediction available")
        return None
    
    # Parse prediction date (the date for which the prediction was made)
    try:
        prediction_date = datetime.fromisoformat(prediction_date_str).date()
    except:
        prediction_date = datetime.strptime(prediction_date_str, "%Y-%m-%d").date()
    
    print(f"\n Prediction made for {prediction_date}")
    print(f"   Predicted production: {predicted_production:.1f} Wh")
    
    # Load actual production for that same date
    actual_production = get_actual_production_yesterday(prediction_date)
    
    if actual_production is None:
        print("\n" + "="*60)
        print("PHASE 4 FAILED: Cannot compare predictions without actual data")
        print("="*60)
        return None
    
    print(f"   Actual production: {actual_production:.1f} Wh")
    
    # Calculate errors
    errors = calculate_errors(predicted_production, actual_production)
    
    print(f"\n Error Analysis for {prediction_date}:")
    print(f"   Predicted: {errors['predicted_wh']:.1f} Wh")
    print(f"   Actual:    {errors['actual_wh']:.1f} Wh")
    print(f"   Error:     {errors['error_wh']:+.1f} Wh ({errors['error_percent']:+.2f}%)")
    print(f"   MAE:       {errors['mae_wh']:.1f} Wh")
    print(f"   Status:    {errors['estimation_type']}")
    
    # Create log entry
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "date": str(prediction_date),
        "predicted_production_wh": predicted_production,
        "actual_production_wh": actual_production,
        "error_wh": errors["error_wh"],
        "mae_wh": errors["mae_wh"],
        "error_percent": errors["error_percent"],
        "estimation_type": errors["estimation_type"]
    }
    
    # Append to error log file
    try:
        with open("error_logs.json", "r") as f:
            all_logs = json.load(f)
    except FileNotFoundError:
        all_logs = []
    
    all_logs.append(log_entry)
    
    with open("error_logs.json", "w") as f:
        json.dump(all_logs, f, indent=2)
    
    print(f"\nError log saved to error_logs.json")
    
    return log_entry


if __name__ == "__main__":
    log_prediction_errors()
