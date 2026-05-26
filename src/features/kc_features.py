from __future__ import annotations

import numpy as np
import pandas as pd

def add_kc_to_df(
    df: pd.DataFrame,
    ghi_col: str = "shortwave_radiation",
    cs_ghi_col: str = "cs_ghi",
    clip_min: float = 0.0,
    clip_max: float = 2.0,
) -> pd.DataFrame:
    """Add instantaneous clearness index KC (=ghi/cs_ghi) to dataframe.

    Parameters
    ----------
    df : pd.DataFrame
        Input dataframe containing measured GHI and clearsky GHI columns.
    ghi_col : str
        Name of the measured GHI column.
    cs_ghi_col : str
        Name of the clearsky GHI column.
    clip_min : float
        Lower bound applied to the ratio (nan replaced by clip_min).
    clip_max : float
        Upper bound applied to the ratio.

    Returns
    -------
    pd.DataFrame
        The original frame with a new "kc" column.
    """

    if ghi_col not in df.columns:
        raise ValueError(f"Column {ghi_col} not found in dataframe")
    if cs_ghi_col not in df.columns:
        raise ValueError(f"Column {cs_ghi_col} not found in dataframe")

    ghi = df[ghi_col].astype(float).values
    cs_ghi = df[cs_ghi_col].astype(float).values

    with np.errstate(divide="ignore", invalid="ignore"):
        kc = np.where(cs_ghi > 0, ghi / cs_ghi, np.nan)

    df["kc"] = np.clip(kc, clip_min, clip_max)
    return df