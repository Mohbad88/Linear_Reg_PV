import joblib
import json
import pandas as pd

model = joblib.load("outputs/model.pkl")
scaler = joblib.load("outputs/scaler.pkl")

with open("outputs/metadata.json", "r", encoding="utf-8") as f:
    metadata = json.load(f)

summary_df = pd.DataFrame(
    {
        "field": ["model_type", "target", "split_date", "intercept"],
        "value": [
            metadata.get("model_type"),
            metadata.get("target"),
            metadata.get("split_date"),
            metadata.get("intercept"),
        ],
    }
)

coeff_df = pd.DataFrame(
    {
        "feature": metadata.get("features", []),
        "coefficient": metadata.get("coefficients", []),
    }
)
if not coeff_df.empty:
    coeff_df["abs_coefficient"] = coeff_df["coefficient"].abs()
    coeff_df = coeff_df.sort_values("abs_coefficient", ascending=False)

metrics = metadata.get("metrics", {})
metrics_df = pd.DataFrame(
    {
        "metric": ["r2", "mae", "rmse"],
        "value": [
            metrics.get("r2"),
            metrics.get("mae"),
            metrics.get("rmse"),
        ],
    }
)

print("\n=== Model Summary ===")
print(summary_df.to_string(index=False))

print("\n=== Performance Metrics ===")
print(metrics_df.to_string(index=False))

print("\n=== Feature Coefficients (sorted by absolute value) ===")
print(coeff_df.to_string(index=False))