from __future__ import annotations

import pandas as pd
from typing import Optional, List

def clean_dataset(
    df,
    pv_col: str = "PV_ELE_IME_I_001",
    zero_check_cols: Optional[List[str]] = None,
    min_production_wh: float = 1000.0,
) -> pd.DataFrame:
    """Drop rows with invalid or too‑low production values.

    Parameters
    ----------
    df : pd.DataFrame
        Input DataFrame indexed by date.
    pv_col : str
        Name of the column containing daily PV production (Wh).
    zero_check_cols : list, optional
        List of columns to verify for nonzero values. If ``None`` a sensible
        default list is used (production + radiation/clearsky features).
    min_production_wh : float
        Minimum acceptable production. Rows with ``pv_col`` below this value
        are removed.

    Returns
    -------
    pd.DataFrame
        Cleaned DataFrame.
    """
    import pandas as _pd  # local import to avoid top-level dependency

    if zero_check_cols is None:
        zero_check_cols = [
            pv_col,
            "shortwave_radiation",
            "direct_radiation",
            "diffuse_radiation",
            "cs_ghi",
            "cs_dni",
            "cs_dhi",
        ]

    # drop rows where all of the specified columns are zero or NaN
    mask = (df[zero_check_cols].fillna(0) == 0).all(axis=1)
    df = df.loc[~mask].copy()

    # enforce minimum daily production
    df = df[df[pv_col] >= min_production_wh]

    return df