from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import requests

from src.data.load_dataset import load_dataset


DEFAULT_LOCAL_PRODUCTION_PATH = "data/raw/dfmodelpierrerozir.csv"


def _safe_get_json(url: str, params: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> Any:
    response = requests.get(url, params=params, headers=headers, timeout=60)
    response.raise_for_status()
    return response.json()


def fetch_open_meteo_hourly(
    start_date: str,
    end_date: str,
    latitude: float,
    longitude: float,
    timezone: str = "UTC",
) -> pd.DataFrame:
    """Fetch hourly weather history from Open-Meteo archive API."""
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start_date,
        "end_date": end_date,
        "timezone": timezone,
        "hourly": [
            "shortwave_radiation",
            "direct_radiation",
            "diffuse_radiation",
            "temperature_2m",
            "cloudcover",
            "windspeed_10m",
            "winddirection_10m",
            "pressure_msl",
        ],
    }

    payload = _safe_get_json(url=url, params=params)
    hourly = payload.get("hourly") or {}
    if "time" not in hourly:
        raise ValueError("Open-Meteo response missing hourly.time field")

    df = pd.DataFrame(hourly)
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df = df.set_index("time").sort_index()
    return df


def _extract_records(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("data", "results", "items", "history"):
            if isinstance(payload.get(key), list):
                return payload[key]
    raise ValueError("Unsupported production API response format")


def fetch_production_history(
    start_date: str,
    end_date: str,
    api_url: str,
    site_key: str,
    site_key_param: str = "site_key",
    site_id: Optional[str] = None,
    api_key: Optional[str] = None,
    timestamp_field: str = "timestamp",
    production_field: str = "production_wh",
) -> pd.DataFrame:
    """Fetch production history from a site API and return hourly series.

    Expected response format:
    - a JSON list of records, or
    - a JSON object containing one of: data/results/items/history.
    """
    params: Dict[str, Any] = {
        "start_date": start_date,
        "end_date": end_date,
        site_key_param: site_key,
    }
    if site_id:
        params["site_id"] = site_id

    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = _safe_get_json(url=api_url, params=params, headers=headers)
    records = _extract_records(payload)
    if not records:
        raise ValueError("Production API returned no records")

    df = pd.DataFrame(records)
    if timestamp_field not in df.columns:
        raise ValueError(f"Missing timestamp field in production data: {timestamp_field}")
    if production_field not in df.columns:
        raise ValueError(f"Missing production field in production data: {production_field}")

    df[timestamp_field] = pd.to_datetime(df[timestamp_field], utc=True)
    df = df[[timestamp_field, production_field]].rename(
        columns={timestamp_field: "time", production_field: "PV_ELE_IME_I_001"}
    )
    df = df.set_index("time").sort_index()

    # Ensure a unique hourly signal even if source granularity is 15-min or irregular.
    df = df.resample("1H").sum(min_count=1)
    return df


def add_hourly_engineered_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add hourly helper columns used later by the daily aggregator."""
    out = df.sort_index().copy()

    out["rad_mean_3h"] = out["shortwave_radiation"].rolling(3, min_periods=1).mean()
    out["rad_std_3h"] = (
        out["shortwave_radiation"].rolling(3, min_periods=1).std().fillna(0.0)
    )
    out["temp_mean_3h"] = out["temperature_2m"].rolling(3, min_periods=1).mean()
    out["wind_mean_3h"] = out["windspeed_10m"].rolling(3, min_periods=1).mean()
    out["rad_diff_1h"] = out["shortwave_radiation"].diff().fillna(0.0)

    day_of_year = out.index.dayofyear
    out["day_cos"] = np.cos(2 * np.pi * day_of_year / 365)

    return out


def load_local_production_series(
    file_path: str,
    production_col: str = "PV_ELE_IME_I_001",
    timestamp_col: Optional[str] = None,
) -> pd.DataFrame:
    """Load local production data and return a clean hourly series."""
    df = load_dataset(file_path)

    if timestamp_col:
        if timestamp_col not in df.columns:
            raise ValueError(f"Missing timestamp column in local production data: {timestamp_col}")
        df[timestamp_col] = pd.to_datetime(df[timestamp_col], utc=True)
        df = df.set_index(timestamp_col)

    if production_col not in df.columns:
        raise ValueError(f"Missing production column in local production data: {production_col}")

    prod = df[[production_col]].copy()
    prod.index = pd.to_datetime(prod.index, utc=True)
    prod = prod.sort_index()
    prod = prod.rename(columns={production_col: "PV_ELE_IME_I_001"})

    # Harmonize at hourly frequency if source is sub-hourly.
    prod = prod.resample("1h").sum(min_count=1)
    return prod


def build_training_frame_weather_api_local_production(
    start_date: str,
    end_date: str,
    latitude: float,
    longitude: float,
    production_file_path: str = DEFAULT_LOCAL_PRODUCTION_PATH,
    production_col: str = "PV_ELE_IME_I_001",
    production_timestamp_col: Optional[str] = None,
) -> pd.DataFrame:
    meteo_df = fetch_open_meteo_hourly(
        start_date=start_date,
        end_date=end_date,
        latitude=latitude,
        longitude=longitude,
    )
    production_df = load_local_production_series(
        file_path=production_file_path,
        production_col=production_col,
        timestamp_col=production_timestamp_col,
    )

    df = meteo_df.join(production_df, how="inner")
    if df.empty:
        raise ValueError(
            "Merged weather/local production dataframe is empty. "
            "Check date range and local production timestamps."
        )

    df = add_hourly_engineered_columns(df)
    return df


def build_training_frame_from_apis(
    start_date: str,
    end_date: str,
    latitude: float,
    longitude: float,
    production_api_url: str,
    site_key: str,
    site_key_param: str = "site_key",
    site_id: Optional[str] = None,
    api_key: Optional[str] = None,
    timestamp_field: str = "timestamp",
    production_field: str = "production_wh",
) -> pd.DataFrame:
    meteo_df = fetch_open_meteo_hourly(
        start_date=start_date,
        end_date=end_date,
        latitude=latitude,
        longitude=longitude,
    )
    production_df = fetch_production_history(
        start_date=start_date,
        end_date=end_date,
        api_url=production_api_url,
        site_key=site_key,
        site_key_param=site_key_param,
        site_id=site_id,
        api_key=api_key,
        timestamp_field=timestamp_field,
        production_field=production_field,
    )

    df = meteo_df.join(production_df, how="inner")
    if df.empty:
        raise ValueError("Merged weather/production dataframe is empty")

    df = add_hourly_engineered_columns(df)
    return df


def build_training_frame_from_env(start_date: str, end_date: str) -> pd.DataFrame:
    """Convenience wrapper for non-interactive runs (local/Azure)."""
    latitude_raw = os.getenv("PV_LATITUDE", "").strip()
    longitude_raw = os.getenv("PV_LONGITUDE", "").strip()
    production_api_url = os.getenv("PV_PRODUCTION_API_URL", "").strip()
    site_key = os.getenv("PV_SITE_KEY", "").strip()
    site_key_param = os.getenv("PV_SITE_KEY_PARAM", "site_key").strip() or "site_key"
    site_id = os.getenv("PV_SITE_ID", "").strip() or None
    api_key = os.getenv("PV_PRODUCTION_API_KEY", "").strip() or None
    timestamp_field = os.getenv("PV_PRODUCTION_TIMESTAMP_FIELD", "timestamp")
    production_field = os.getenv("PV_PRODUCTION_VALUE_FIELD", "production_wh")

    if not latitude_raw or not longitude_raw:
        raise ValueError(
            "PV_LATITUDE and PV_LONGITUDE are required to fetch weather data"
        )

    latitude = float(latitude_raw)
    longitude = float(longitude_raw)

    if not production_api_url:
        raise ValueError(
            "PV_PRODUCTION_API_URL is required to fetch production history"
        )

    if not site_key:
        raise ValueError(
            "PV_SITE_KEY is required to fetch production history"
        )

    return build_training_frame_from_apis(
        start_date=start_date,
        end_date=end_date,
        latitude=latitude,
        longitude=longitude,
        production_api_url=production_api_url,
        site_key=site_key,
        site_key_param=site_key_param,
        site_id=site_id,
        api_key=api_key,
        timestamp_field=timestamp_field,
        production_field=production_field,
    )


def build_training_frame_weather_api_local_from_env(
    start_date: str,
    end_date: str,
    production_file_path: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
) -> pd.DataFrame:
    latitude_raw = os.getenv("PV_LATITUDE", "").strip()
    longitude_raw = os.getenv("PV_LONGITUDE", "").strip()
    env_production_path = os.getenv("PV_LOCAL_PRODUCTION_PATH", "").strip()
    production_col = os.getenv("PV_LOCAL_PRODUCTION_COLUMN", "PV_ELE_IME_I_001").strip()
    production_timestamp_col = (
        os.getenv("PV_LOCAL_TIMESTAMP_COLUMN", "").strip() or None
    )

    # Latitude/longitude: CLI args take priority, then env vars, then error.
    if latitude is None:
        if not latitude_raw:
            raise ValueError("PV_LATITUDE env var is required when --latitude is not provided")
        latitude = float(latitude_raw)
    if longitude is None:
        if not longitude_raw:
            raise ValueError("PV_LONGITUDE env var is required when --longitude is not provided")
        longitude = float(longitude_raw)

    resolved_production_path = (
        production_file_path
        or env_production_path
        or DEFAULT_LOCAL_PRODUCTION_PATH
    )

    return build_training_frame_weather_api_local_production(
        start_date=start_date,
        end_date=end_date,
        latitude=latitude,
        longitude=longitude,
        production_file_path=resolved_production_path,
        production_col=production_col,
        production_timestamp_col=production_timestamp_col,
    )