from sklearn.preprocessing import StandardScaler
import pandas as pd
import numpy as np


def scale_features(
    X_train: pd.DataFrame,
    X_test: pd.DataFrame,
    scaler: StandardScaler | None = None,
) -> tuple[StandardScaler, np.ndarray, np.ndarray]:
    """Fit (or reuse) a scaler and transform train/test features.

    Returns ``(scaler, X_train_scaled, X_test_scaled)``.  ``scaler`` is
    created if ``None``.
    """

    if scaler is None:
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
    else:
        X_train_scaled = scaler.transform(X_train)

    X_test_scaled = scaler.transform(X_test)

    return scaler, X_train_scaled, X_test_scaled


def make_predictions(model, X: pd.DataFrame | np.ndarray) -> np.ndarray:
    """Return model predictions; accept pandas/ndarray inputs."""
    arr = X
    if isinstance(X, pd.DataFrame):
        arr = X.values
    return model.predict(arr)
