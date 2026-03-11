import numpy as np
import pandas as pd


def aggregate_daily(df: pd.DataFrame) -> pd.DataFrame:
    """Convert a high-frequency dataset into daily aggregates.

    The previous implementation accepted arbitrary rules; the notebook
    specifies a fixed set of sum/mean aggregations and a post‑processing step
    to compute ``kc_day``.  This helper reproduces that behaviour and also
    normalises the index so that subsequent date-based splitting works
    reliably.
    """

    # columns to sum and mean as in the original notebook
    sum_cols = [
        'PV_ELE_IME_I_001',
        'shortwave_radiation',
        'direct_radiation',
        'diffuse_radiation',
        'cs_ghi',
        'cs_dni',
        'cs_dhi',
        'rad_mean_3h',
        'rad_std_3h',
        'temp_mean_3h',
        'wind_mean_3h',
        'rad_diff_1h',
    ]
    mean_cols = [
        'temperature_2m',
        'cloudcover',
        'windspeed_10m',
        'winddirection_10m',
        'pressure_msl',
        'day_cos',
    ]

    rules: dict[str, str] = {}
    for c in sum_cols:
        rules[c] = 'sum'
    for c in mean_cols:
        rules[c] = 'mean'

    df_daily = df.groupby(df.index.date).agg(rules)
    df_daily.index = pd.to_datetime(df_daily.index)

    # compute kc_day and sanitise
    with np.errstate(divide='ignore', invalid='ignore'):
        df_daily['kc_day'] = df_daily['shortwave_radiation'] / df_daily['cs_ghi']
    df_daily['kc_day'] = df_daily['kc_day'].replace([np.inf, -np.inf], 0).fillna(0)

    # normalise index to midnight
    df_daily.index = pd.to_datetime(df_daily.index).normalize()

    return df_daily